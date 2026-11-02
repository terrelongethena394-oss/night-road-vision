"""Integrate immutable verified road kernel with existing800x480 LCD drivers."""
from pathlib import Path
import os,re,struct,shutil,subprocess
import numpy as np
from PIL import Image
from road_arm_common import ROOT as NN,read,write,sha
ROOT=Path('E:/FPGA_Enhance_Work/road_lcd_static_20261027')
HERE=Path(__file__).resolve().parent
OLD=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
PLATFORM=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
TOOLS=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
def main():
    ROOT.mkdir(exist_ok=False);source=ROOT/'source';source.mkdir();arm=read(NN/'arm_compile_complete_r2.json');proof=read(NN/'board_batch_r2/complete.json')
    assert arm['elf_sha256']==proof['elf_sha256']
    for name in ['road_fp32.c','road_fp32.h','road_graph.h','road_probe_config.h','lscript.ld']:
        assert sha(NN/'arm_probe_r2/source'/name)==arm['source_sha256'][name];shutil.copy2(NN/'arm_probe_r2/source'/name,source/name)
    for name in ['road_lcd.c','road_lcd.h','road_lcd_draw.c','road_lcd_draw.h','road_lcd_draw_host.c']:shutil.copy2(HERE/name,source/name)
    for name in ['display_ctrl','clk_wiz','vdma_api']:shutil.copytree(OLD/'app_src'/name,source/name)
    # Add a bounded lock wait to the isolated vendor clock-driver copy.
    p=source/'clk_wiz/clk_wiz.c';code=p.read_bytes().decode('gb18030');assert code.count('while(1)')==1
    code=code.replace('#include "xparameters.h"','#include "xparameters.h"\n#include "sleep.h"')
    code=code.replace('while(1){','for(u32 road_poll=0;road_poll<200000U;road_poll++){')
    needle='status = XClk_Wiz_ReadReg(clk_cfg_ptr->BaseAddr,CLK_SR_OFFSET);';assert needle in code
    code=code.replace(needle,needle+'\n        usleep(10);');p.write_bytes(code.encode('gb18030'))
    p=source/'road_lcd.c';code=p.read_text(encoding='utf-8');code=code.replace('clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);','clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);\n if(!(Xil_In32(XPAR_CLK_WIZ_0_BASEADDR+CLK_SR_OFFSET)&1U))return 8;');p.write_text(code,encoding='utf-8')
    app=(NN/'arm_probe_r2/source/road_arm_probe.c').read_text();app=app.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_lcd.h"\n#include "road_lcd_draw.h"')
    app=app.replace('M_INPUT_EXPECTED_FNV,M_TRACE_ENABLE,M_BOX320};','M_INPUT_EXPECTED_FNV,M_TRACE_ENABLE,M_BOX320,\n M_LCD_ID,M_FRAME_SLOT,M_FRAME_ADDR,M_RENDER_LO,M_RENDER_HI,M_DMA_ERRORS,M_CASE_ID,M_FRAME_FNV,M_LCD_STATUS};')
    app=app.replace('XTime begin,p0,p1,n0,n1,end,finished;int n,error;','XTime begin,p0,p1,n0,n1,end,finished,r0,r1;int n,error;\n uint32_t lcd_id=0,slot=0,frame_hash=0,dma=0;')
    app=app.replace('mail[M_VERSION]=1;mail[M_STATE]=1;','mail[M_VERSION]=2;mail[M_STATE]=0;')
    old='xil_printf("ROAD_ARM_PROBE_READY V1\\r\\n");'
    new='''error=road_lcd_init(&lcd_id);mail[M_LCD_ID]=lcd_id;
  if(error){mail[M_ERROR]=(uint32_t)(100+error);mail[M_STATE]=4;barrier();for(;;){mail[M_HEARTBEAT]++;usleep(1000);}}
  mail[M_FRAME_ADDR]=ROAD_LCD_FRAME_BASE;mail[M_FRAME_SLOT]=0;mail[M_LCD_STATUS]=1;mail[M_STATE]=1;barrier();
  xil_printf("ROAD_LCD_STATIC_READY V2\\r\\n");'''
    assert old in app;app=app.replace(old,new)
    old='mail[M_SEQUENCE]++;barrier();mail[M_STATE]=3;barrier();'
    new='''XTime_GetTime(&r0);
    error=road_lcd_present((const uint32_t *)INPUT_ADDR,(const float *)BOX400_ADDR,n,(unsigned)(((finished-begin)*1000U+COUNTS_PER_SECOND/2U)/COUNTS_PER_SECOND),mail[M_CASE_ID],&slot,&frame_hash,&dma);
    XTime_GetTime(&r1);ticks(M_RENDER_LO,M_RENDER_HI,r1-r0);mail[M_DMA_ERRORS]=dma;
    if(error){mail[M_ERROR]=(uint32_t)(200+error);mail[M_STATE]=4;barrier();continue;}
    mail[M_FRAME_SLOT]=slot;mail[M_FRAME_ADDR]=ROAD_LCD_FRAME_BASE+slot*ROAD_LCD_FRAME_BYTES;mail[M_FRAME_FNV]=frame_hash;mail[M_LCD_STATUS]=2;
    mail[M_SEQUENCE]++;barrier();mail[M_STATE]=3;barrier();'''
    assert app.count(old)==1;app=app.replace(old,new);(source/'road_lcd_main.c').write_text(app,encoding='ascii')
    assert sha(source/'road_fp32.c')==arm['host_verified_kernel_sha256']
    shutil.copy2(OLD/'camera.bit',ROOT/'display.bit');shutil.copy2(OLD/'camera.xsa',ROOT/'display.xsa');shutil.copy2(OLD/'ps7_init.tcl',ROOT/'ps7_init.tcl');shutil.copy2(OLD/'Xilinx.spec',ROOT/'Xilinx.spec')
    assert sha(ROOT/'display.bit')=='676f575fed31e20e0b6b5a4db0b5bcc62718686e32756c17ce552685b9257427'
    # Compile portable rasterizer and verify independent coordinate/color controls.
    host=ROOT/'host';host.mkdir();gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
    env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(source),str(source/'road_lcd_draw.c'),str(source/'road_lcd_draw_host.c'),'-o',str(host/'render.exe'),'-lm']
    run=subprocess.run(cmd,env=env,capture_output=True,text=True);(host/'build.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
    y,x=np.indices((240,400));rgb=np.stack([x%256,y%256,(x+y)%256],2).astype(np.uint32);words=rgb[:,:,0]|(rgb[:,:,1]<<8)|(rgb[:,:,2]<<16)
    words.astype('<u4').tofile(host/'gradient.u32');np.array([[50,40,100,80,.9,1]],'<f4').tofile(host/'control_boxes.f32')
    run=subprocess.run([str(host/'render.exe'),str(host/'gradient.u32'),str(host/'control_boxes.f32'),str(host/'control.bgr'),'2300','1'],capture_output=True,text=True,check=True)
    assert 'GUARDS_PASS' in run.stdout;frame=np.fromfile(host/'control.bgr',np.uint8).reshape(480,800,3)
    assert frame[200,500].tolist()==[94,100,250] and frame[100,100].tolist()==[255,230,0]
    first=read(NN/'export_complete.json')['fixtures'][0]['name'];run=subprocess.run([str(host/'render.exe'),str(NN/'cases'/first/'input400.u32'),str(NN/'board_batch_r2'/first/'boxes400.f32'),str(host/'preview.bgr'),'2267','1'],capture_output=True,text=True,check=True)
    assert 'GUARDS_PASS' in run.stdout;Image.fromarray(np.fromfile(host/'preview.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(ROOT/'host_preview.png')
    write(ROOT/'renderer_host_proof.json',dict(status='GUARDS_PIXEL_CHANNEL_ORDER_AND_2X_BOX_COORDINATES_PASS',checks=['Guard bytes unchanged','BGR source pixel mapped2x','Box50,40,100,80 maps100,80,200,160 with cyan CAR border'],
          source_sha256=sha(source/'road_lcd_draw.c'),preview='Host render only, not a screen capture'))
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-g','-fstack-usage','-I'+str(source),'-I'+str(PLATFORM/'bspinclude/include')]
    obj=ROOT/'obj';obj.mkdir();objects=[];commands=[];logs=[];armgcc=TOOLS/'arm-none-eabi-gcc.exe'
    files=[source/n for n in ['road_fp32.c','road_lcd.c','road_lcd_draw.c','road_lcd_main.c']]+[p for d in ['display_ctrl','clk_wiz','vdma_api'] for p in sorted((source/d).glob('*.c'))]
    for p in files:
        target=obj/('_'.join(p.relative_to(source).parts)+'.o');strict=['-Wextra','-Werror'] if p.parent==source else []
        cmd=[str(armgcc),*flags,*strict,'-c',str(p),'-o',str(target)];run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr)
        (ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr;objects.append(str(target))
    cmd=[str(armgcc),*flags[:3],'-Wl,-build-id=none','-specs='+str(ROOT/'Xilinx.spec'),'-Wl,-T,'+str(source/'lscript.ld'),'-Wl,-Map,'+str(ROOT/'road_lcd.map'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(ROOT/'road_lcd.elf'),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(ROOT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,run.stderr
    raw=(ROOT/'road_lcd.elf').read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,n=struct.unpack_from('<HH',raw,42);regions=[]
    for i in range(n):
        kind,o,va,pa,fs,ms,fl,al=struct.unpack_from('<8I',raw,off+i*size)
        if kind==1 and ms:assert 0x100000<=pa<pa+ms<=0x1000000;regions.append([pa,pa+ms])
    assert 0x02000000+3*800*480*3<0x03000000
    write(ROOT/'offline_complete.json',dict(status='ROAD_STATIC_LCD_COMPILED_AND_HOST_RENDERER_VERIFIED_NOT_BOARD_VERIFIED',elf_sha256=sha(ROOT/'road_lcd.elf'),
          bit_sha256=sha(ROOT/'display.bit'),kernel_sha256=sha(source/'road_fp32.c'),prior_verified_kernel_sha256=arm['host_verified_kernel_sha256'],
          renderer_sha256=sha(source/'road_lcd_draw.c'),elf_regions=regions,frame_regions=[0x02000000,0x02000000+3*800*480*3],commands=commands,
          weights_path=str(NN/'weights.f32'),weights_sha256=sha(NN/'weights.f32'),board_downloaded=False,sd_written=False,mail_version=2))
    print('ROAD_STATIC_LCD_COMPILED',len(raw),regions,flush=True)
if __name__=='__main__':main()
