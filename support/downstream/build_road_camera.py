"""Build live-preview/frozen-result application; preserve all previous programs."""
import os,shutil,subprocess,re,struct,time
from pathlib import Path
import numpy as np
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT as LCD,PLATFORM,TOOLS
ROOT=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
OLD=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')

def main():
    ROOT.mkdir(exist_ok=False);source=ROOT/'source';source.mkdir();start=time.monotonic()
    assert sha(LCD/'source/road_fp32.c')=='c8fd60cda9148f779b1ea6c89c1264e5e0c9f3966c0c84d6d04ef2fd632de47a'
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_NEW_CAMERA_BUILD_AND_INFERENCE',model_sha256=sha(NN/'weights.f32'),original_kernel_sha256=sha(LCD/'source/road_fp32.c'),
       scope='ARM FP32 road detection with cooperative live preview. Left latest400x240 camera snapshot; right input snapshot associated with latest completed boxes. No old boxes drawn on live image.',
       kernel_change='Only callback after each Conv outputrow and after everyoperator. Arithmetic and FP32decode/NMS unchanged. Must pass byte-exact host tests and physical frozen-input tests.',
       timestamp='Snapshot AGE counts from CPU downsample completion, not exposure time. Detection elapsed includes preview work; pause durations excluded and flagged.',
       preview_period_ms=150,raw_camera=True,enhancement_enabled=False,sd_write=False,flash_write=False))
    for name in ['road_fp32.h','road_graph.h','road_probe_config.h','lscript.ld']:shutil.copy2(LCD/'source'/name,source/name)
    for name in ['road_camera.h','road_camera_io.h','road_camera_io.c','road_camera_main.c','road_camera_average.c','road_camera_average_host.c','road_camera_draw_host.c']:shutil.copy2(HERE/name,source/name)
    for name in ['display_ctrl','clk_wiz','vdma_api']:shutil.copytree(LCD/'source'/name,source/name)
    for name in ['emio_sccb_cfg','ov5640']:shutil.copytree(OLD/'app_src'/name,source/name)
    code=(LCD/'source/road_fp32.c').read_text();needle='#include "road_fp32.h"'
    hooks='''
static void (*road_service_callback)(void *);
static void *road_service_opaque;
void road_set_service(void (*fn)(void *),void *opaque){road_service_callback=fn;road_service_opaque=opaque;}
static void road_poll_service(void){if(road_service_callback)road_service_callback(road_service_opaque);}
'''
    code=code.replace(needle,needle+hooks)
    needle='for(y=0;y<out->h;y++)for(x=0;x<out->w;){';assert code.count(needle)==1;code=code.replace(needle,'for(y=0;y<out->h;y++){for(x=0;x<out->w;){')
    needle='    x+=tile;\n  }\n}';assert code.count(needle)==1;code=code.replace(needle,'    x+=tile;\n  }road_poll_service();\n  }\n}')
    needle='    if(trace)trace(i,b,(uint32_t)(out->h*out->w*out->c4),opaque);';assert code.count(needle)==1;code=code.replace(needle,needle+'\n    road_poll_service();')
    (source/'road_fp32.c').write_text(code,encoding='ascii')
    draw=(LCD/'source/road_lcd_draw.c').read_text();draw=draw[:draw.index('void road_lcd_waiting')]
    draw=draw.replace('#include "road_lcd_draw.h"','#include "road_camera.h"')
    draw=draw.replace('static const uint8_t percent[7]={25,26,2,4,8,11,19};','static const uint8_t percent[7]={25,26,2,4,8,11,19};static const uint8_t period[7]={0,0,0,0,0,6,6};')
    draw=draw.replace("else if(s[n]=='%')g=percent;","else if(s[n]=='%')g=percent;else if(s[n]=='.')g=period;")
    draw+=(HERE/'road_camera_draw_body.inc').read_text();(source/'road_camera_draw.c').write_text(draw,encoding='ascii')
    host=ROOT/'host';host.mkdir();env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','');commands=[]
    harness=(HERE/'road_fp32_host.c').read_text();harness=harness.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_camera.h"\nstatic unsigned calls;static volatile unsigned scratch[32];\nstatic void preview_stub(void *p){(void)p;calls++;scratch[calls%32]^=calls;}')
    harness=harness.replace('road_input320(rgb,arena);start=clock();','road_input320(rgb,arena);road_set_service(preview_stub,0);start=clock();')
    harness=harness.replace('free(weights);free(arena);','printf("COOPERATIVE_CALLBACKS=%u\\n",calls);if(!calls)return 16;free(weights);free(arena);')
    (source/'road_camera_kernel_host.c').write_text(harness,encoding='ascii')
    flags=['-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(source)]
    def build(exe,files,extra=[]):
        cmd=[str(GCC),*flags,*extra,*[str(source/f) for f in files],'-o',str(host/exe),'-lm'];p=subprocess.run(cmd,env=env,capture_output=True,text=True);(host/(exe+'.build.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;commands.append(cmd)
    build('kernel.exe',['road_fp32.c','road_camera_kernel_host.c']);build('render.exe',['road_camera_draw.c','road_camera_draw_host.c']);build('average.exe',['road_camera_average.c','road_camera_average_host.c'])
    proof=[]
    for fixture in read(NN/'export_complete.json')['fixtures']:
        name=fixture['name'];out=host/name;out.mkdir();trace=out/'trace';trace.mkdir()
        p=subprocess.run([str(host/'kernel.exe'),str(NN/'weights.f32'),str(NN/'cases'/name/'input400.u32'),str(out),str(trace)],capture_output=True,text=True,check=True)
        assert 'COOPERATIVE_CALLBACKS=' in p.stdout
        for file in (NN/'host_r2'/name/'trace').iterdir():assert file.read_bytes()==(trace/file.name).read_bytes(),(name,file.name)
        for file in ['decoded.f32','boxes320.f32','boxes400.f32','input320.rgb']:assert (out/file).read_bytes()==(NN/'host_r2'/name/file).read_bytes(),(name,file)
        proof.append(dict(name=name,all86_tensors_and_decode_nms_bytes_exact=True,stdout=p.stdout.strip()));print('CAMERA_COOPERATIVE_HOST_ALL86_EXACT',name,flush=True)
    rng=np.random.default_rng(2026102714);average=[]
    for tag,a in [('black',np.zeros((480,800,3),np.uint8)),('white',np.full((480,800,3),255,np.uint8)),('random',rng.integers(0,256,(480,800,3),dtype=np.uint8))]:
        a.tofile(host/(tag+'.bgr'));p=subprocess.run([str(host/'average.exe'),str(host/(tag+'.bgr')),str(host/(tag+'.u32'))],capture_output=True,text=True,check=True)
        b=((a.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32);expected=b[:,:,2]|(b[:,:,1]<<8)|(b[:,:,0]<<16)
        assert (host/(tag+'.u32')).read_bytes()==expected.astype('<u4').tobytes();average.append(dict(name=tag,all384000_bytes_exact=True))
    y,x=np.indices((240,400));live=np.stack([x%256,y%256,(x+y)%256],2).astype(np.uint32);words=live[:,:,0]|(live[:,:,1]<<8)|(live[:,:,2]<<16);words.astype('<u4').tofile(host/'live_control.u32')
    (words^0x00ffffff).astype('<u4').tofile(host/'result_control.u32');np.array([[50,40,100,80,.9,1]],'<f4').tofile(host/'control_boxes.f32')
    ui=np.array([37,3,35,2550,2900,65,1,1,0,0,1],'<u4');ui.tofile(host/'control_ui.u32')
    p=subprocess.run([str(host/'render.exe'),str(host/'live_control.u32'),str(host/'result_control.u32'),str(host/'control_boxes.f32'),str(host/'control_ui.u32'),str(host/'control_frame.bgr')],capture_output=True,text=True,check=True);assert 'GUARDS_PASS' in p.stdout
    frame=np.fromfile(host/'control_frame.bgr',np.uint8).reshape(480,800,3)
    assert frame[140,450].tolist()==[255,230,0] # CAR border only on right.
    for yy,xx in [(140,50),(200,250),(339,399)]:
        v=int(words[yy-100,xx]);assert frame[yy,xx].tolist()==[(v>>16)&255,(v>>8)&255,v&255]
    first=read(NN/'export_complete.json')['fixtures'][0]['name'];ui=np.array([37,1,38,2550,2900,65,14,1,1,0,1],'<u4');ui.tofile(host/'preview_ui.u32')
    subprocess.run([str(host/'render.exe'),str(host/'live_control.u32'),str(NN/'cases'/first/'input400.u32'),str(NN/'host_r2'/first/'boxes400.f32'),str(host/'preview_ui.u32'),str(host/'preview.bgr')],capture_output=True,text=True,check=True)
    from PIL import Image
    Image.fromarray(np.fromfile(host/'preview.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(ROOT/'host_design_preview.png')
    write(ROOT/'host_complete.json',dict(status='COOPERATIVE_KERNEL_ALL8_ALL86_BYTES_EXACT_AND_CAMERA_MEAN_RENDERER_CONTROLS_PASS',fixtures=proof,average=average,renderer='guards, sourceRGB/BGR, native400coordinates, right-onlybox',commands=commands,board_run=False))
    for name in ['display.bit','display.xsa','ps7_init.tcl','Xilinx.spec']:shutil.copy2(LCD/name,ROOT/name)
    assert sha(ROOT/'display.bit')==sha(OLD/'camera.bit')
    obj=ROOT/'obj';obj.mkdir();objects=[];logs=[];armflags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(source),'-I'+str(PLATFORM/'bspinclude/include')]
    files=[source/n for n in ['road_fp32.c','road_camera_main.c','road_camera_io.c','road_camera_draw.c','road_camera_average.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api','emio_sccb_cfg','ov5640'] for p in sorted((source/d).glob('*.c'))]
    for p in files:
        target=obj/('_'.join(p.relative_to(source).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==source else []
        cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*armflags,*strict,'-c',str(p),'-o',str(target)];run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr;objects.append(str(target))
    elf=ROOT/'road_camera.elf';cmd=[str(TOOLS/'arm-none-eabi-gcc.exe'),*armflags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(source/'lscript.ld'),'-Wl,-Map,'+str(ROOT/'road_camera.map'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(elf),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr
    raw=elf.read_bytes();phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);regions=[]
    for i in range(n):
        kind,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;regions.append([pa,pa+mem])
    memory=[('frames',0x02000000,3*1152000),('capture',0x06000000,3*1152000),('input',0x10000000,384000),('weights',0x11000000,7062464),('arena',0x12000000,3276800),('decode',0x13000000,226800),('prep',0x13200000,307200),('candidates',0x13400000,6300*28),('keep',0x13500000,300*28),('box400',0x13600000,7200),('box320',0x13610000,7200),('mail',0x13800000,4096),('trace',0x14000000,19844800),('live',0x16000000,384000),('result',0x16100000,384000),('resultbox',0x16200000,7200),('saveddecode',0x16300000,226800),('savedheads',0x16400000,235200),('ui',0x16500000,44)]
    for i,(name,a,b) in enumerate(memory):
        assert a+b<=0x40000000
        for nn,c,d in memory[i+1:]:assert a+b<=c or c+d<=a,(name,nn)
    write(ROOT/'offline_complete.json',dict(status='CAMERA_COOPERATIVE_APP_HOST_PROVEN_AND_ARM_COMPILED_NOT_BOARD_RUN',elf_sha256=sha(elf),bit_sha256=sha(ROOT/'display.bit'),weights_sha256=sha(NN/'weights.f32'),kernel_sha256=sha(source/'road_fp32.c'),
       original_kernel_sha256=sha(LCD/'source/road_fp32.c'),source_sha256={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},commands=commands,elf_regions=regions,memory=memory,seconds=time.monotonic()-start,
       weights_path=str(NN/'weights.f32'),board_run=False,sd_written=False,rollback=str(LCD/'00_install_ram.cmd')))
    print('ROAD_CAMERA_OFFLINE_COMPILED_AND_HOST_PROVEN',sha(elf),flush=True)
if __name__=='__main__':main()
