"""Isolated ABI23 fixed-photo four-pass build; preserve ABI22 and SD."""
from pathlib import Path
import os,re,shutil,struct,subprocess,sys,datetime
from road_accuracy_common import ROOT,APP as OLD,read,write,sha

HERE=Path(__file__).resolve().parent
APP=ROOT/'firmware'

def main_source(s):
    assert 'm[M_VERSION]=22;' in s
    s=s.replace('#include "road_detail_config.h"','#include "road_detail_config.h"\n#include "road_vehicle_multiview.h"\n#define RVM_TILE(i) (0x1A000000U+(i)*0x60000U)\n#define RVM_DECODE(i) (0x1A120000U+(i)*0x40000U)\n#define RVM_BASELINE 0x1A200000U\nstatic RoadBox rvm_tiles[900];\nstatic int rvm_counts[3];\nstatic uint32_t rvm_baseline_count;')
    s=s.replace('ui.detail_mode=result_detail;','ui.detail_mode=result_detail;ui.baseline_count=rvm_baseline_count;')
    old='(const float *)RC_RESULT_BOX,&ui)';assert old in s;s=s.replace(old,'(const float *)RC_RESULT_BOX,(const float *)RVM_BASELINE,&ui)')
    s=s.replace('if(detail>1U||(detail&&pipe==1U))fatal(34);','if((detail!=0U&&detail!=2U)||(detail&&pipe==1U))fatal(34);if(detail&&!injected)fatal(42);')
    s=s.replace('if(detail)Xil_DCacheInvalidateRange(RC_ROI_INPUT,RC_RAW_BYTES);','if(detail){unsigned q;for(q=0;q<3;q++)Xil_DCacheInvalidateRange(RVM_TILE(q),RC_RAW_BYTES);}')
    old='m[97]=detail?hash((const void *)RC_ROI_INPUT,RC_RAW_BYTES):0;if(injected&&detail&&m[98]&&m[98]!=m[97])fatal(36);'
    assert old in s;s=s.replace(old,'m[97]=0;if(detail){unsigned q;for(q=0;q<3;q++){m[133+q]=hash((const void *)RVM_TILE(q),RC_RAW_BYTES);if(m[136+q]&&m[133+q]!=m[136+q])fatal(36);}}')
    # AP-consistent low threshold before fusion; operation-point filter happens
    # only after fusion. Raw single-pass screen retains confidence .25.
    old='300,.25f,.6f);if(count<0)fatal(21);';assert old in s
    s=s.replace(old,'300,detail?.001f:.25f,.6f);if(count<0)fatal(21);')
    first=s.index(' if(detail){\n  XTime a,b;int nr,nf=count')
    last=s.index(' m[99]=detail;',first)
    replacement=''' if(detail){
  XTime a,b;int nf=count,k,t,kept=0;uint32_t o=0;
  memcpy((void *)RC_FULL_BOX,(const void *)RC_KEEP,(uint32_t)nf*sizeof(RoadBox));
  memcpy((void *)RC_FULL_DECODE,(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);memcpy((void *)RC_FULL_PREP,(const void *)RC_PREP,320U*320U*3U);
  for(k=0;k<3;k++){const RoadTensor *tt=ROAD_T+ROAD_HEADS[k];uint32_t size=(uint32_t)tt->h*tt->w*tt->c4*4U;memcpy((void *)(RC_FULL_HEAD+o),(const float *)RC_ARENA+tt->off,size);o+=size;}
  for(t=0;t<3;t++){
   a=now();road_preprocess400((const uint32_t *)RVM_TILE(t),(uint8_t *)RC_PREP);road_input320((const uint8_t *)RC_PREP,(float *)RC_ARENA);
   road_pl_begin();a=now();if(road_forward((const float *)RC_WEIGHT,(float *)RC_ARENA,0,0))fatal(37);b=now();network_ticks+=b-a;m[104]+=m[73];
   road_decode((const float *)RC_ARENA,(float *)RC_DECODE);memcpy((void *)RVM_DECODE(t),(const void *)RC_DECODE,ROAD_CANDIDATES*9U*4U);
   rvm_counts[t]=road_nms((const float *)RC_DECODE,(RoadBox *)RC_CANDIDATES,(RoadBox *)RC_KEEP,300,.001f,.6f);if(rvm_counts[t]<0)fatal(38);
   road_boxes_to400((RoadBox *)RC_KEEP,rvm_counts[t]);memcpy(rvm_tiles+t*300,(const void *)RC_KEEP,(uint32_t)rvm_counts[t]*sizeof(RoadBox));m[139+t]=(uint32_t)rvm_counts[t];
   if(hash((const void *)RVM_TILE(t),RC_RAW_BYTES)!=m[133+t])fatal(41);
   Xil_DCacheFlushRange(RVM_DECODE(t),ROAD_CANDIDATES*9U*4U);
  }
  count=road_vehicle_multiview((const RoadBox *)RC_FULL_BOX,nf,rvm_tiles,rvm_counts,.75f,(RoadBox *)RC_FUSED_BOX,300);if(count<0)fatal(40);
  for(k=0;k<count;k++)if(((RoadBox *)RC_FUSED_BOX)[k].score>=.25f)((RoadBox *)RC_KEEP)[kept++]=((RoadBox *)RC_FUSED_BOX)[k];count=kept;
  rvm_baseline_count=0;
  for(k=0;k<nf;k++)if(((const RoadBox *)RC_FULL_BOX)[k].score>=.25f){
   const RoadBox *v=(const RoadBox *)RC_FULL_BOX+k;float *p=(float *)RVM_BASELINE+rvm_baseline_count*6;
   p[0]=v->x1;p[1]=v->y1;p[2]=v->x2;p[3]=v->y2;p[4]=v->score;p[5]=(float)v->cls;rvm_baseline_count++;
  }
  m[142]=rvm_baseline_count;m[143]=RVM_BASELINE;Xil_DCacheFlushRange(RVM_BASELINE,rvm_baseline_count*24U);
  Xil_DCacheFlushRange(RC_FULL_DECODE,ROAD_CANDIDATES*9U*4U);
 }else{rvm_baseline_count=0;m[142]=0;}
'''
    s=s[:first]+replacement+s[last:]
    s=s.replace('m[M_VERSION]=22;','m[M_VERSION]=23;').replace('ROAD_RETINEX_READY V22','ROAD_ACCURACY_READY V23').replace('m[94]=0U;','m[94]=2U;')
    return s

def draw_source(s):
    s=s.replace('const float *boxes,const RoadCameraUI *u)','const float *boxes,const float *baseline,const RoadCameraUI *u)')
    s=s.replace('u->count>300U||','u->count>300U||u->baseline_count>300U||(u->baseline_count&&!baseline)||')
    first=s.index(' if(u->has_result)for(i=0;i<(int)u->count;i++){\n  const float *b=boxes+6*i;')
    last=s.index(' text(f,10,14,',first)
    block=s[first:last].replace(' if(u->has_result)for(i=0;i<(int)u->count;i++){\n  const float *b=boxes+6*i;', ' if(u->has_result){int side;for(side=0;side<2;side++){int column=400*side;unsigned count=side?u->count:u->baseline_count;const float *source=side?boxes:baseline;for(i=0;i<(int)count;i++){\n  const float *b=source+6*i;')
    block=block.replace('400+','column+').replace('401+','column+1+')
    block=block.replace('  int y1=', '  int y1=')  # Keep original half-up raster rounding.
    block=block.rstrip()+'}}\n'
    s=s[:first]+block+s[last:]
    marker=' memset(f,0,RC_FRAME_BYTES);'
    validation=' if(u->has_result)for(i=0;i<(int)u->baseline_count;i++){for(k=0;k<6;k++)if(!isfinite(baseline[i*6+k]))return -2;if(baseline[i*6+5]<0||baseline[i*6+5]>3||baseline[i*6+5]!=(float)(int)baseline[i*6+5])return -3;}\n'
    s=s.replace(marker,validation+marker)
    s=s.replace('u->is_test?"STATIC RAW":"LIVE RAW"','u->is_test?"RAW SINGLE DET":"LIVE RAW"')
    s=s.replace('u->detail_mode?"DETAIL X2 / EXPERIMENT"','u->detail_mode?"ENH VIEW 4 PASS DET"')
    s=s.replace('"DETECT %u MS BOXES %u"','"4PASS %u MS BOXES %u"')
    s=s.replace('if(u->paused)strcpy(s,"PAUSED");','if(u->paused)snprintf(s,sizeof(s),"RAW BOXES %u",(unsigned)u->baseline_count);')
    start=s.index('  if(!u->enh_alpha)snprintf(s,sizeof(s),"BYPASS')
    end=s.index('  text(f,10,440,s,2,0xFFFFFF);',start)
    s=s[:start]+'  strcpy(s,"DISPLAY ENHANCED  DETECTOR INPUT RAW");\n'+s[end:]
    return s

def main():
    assert read(ROOT/'selected.json')['chosen']['tag']=='three_raw_w75'
    rebuild='--rebuild' in sys.argv
    if APP.exists():
        assert rebuild and (APP/'arm_complete.json').exists()
        shutil.copy2(APP/'arm_complete.json',ROOT/('build_before_renderer_fix_'+datetime.datetime.now().strftime('%H%M%S')+'.json'))
    APP.mkdir(exist_ok=rebuild);shutil.copytree(OLD/'source',APP/'source',dirs_exist_ok=rebuild);(APP/'runtime').mkdir(exist_ok=rebuild);shutil.copy2(OLD/'runtime/weights.f32',APP/'runtime/weights.f32')
    for name in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/name,APP/name)
    src=APP/'source'
    for n in ['road_vehicle_multiview.c','road_vehicle_multiview.h']:shutil.copy2(HERE/n,src/n)
    p=src/'road_camera_main.c';p.write_text(main_source(p.read_text()),encoding='ascii')
    p=src/'road_camera.h';s=p.read_text().replace('} RoadCameraUI;',' uint32_t baseline_count;\n} RoadCameraUI;').replace('const float *,const RoadCameraUI *);','const float *,const float *,const RoadCameraUI *);');p.write_text(s,encoding='ascii')
    p=src/'road_camera_draw.c';p.write_text(draw_source(p.read_text()),encoding='ascii')
    p=src/'road_camera_draw_host.c';s=p.read_text().replace('float *boxes;','float *boxes,*baseline;').replace('argc!=6','argc!=7').replace('argv[4],&ui','argv[5],&ui').replace('boxes=malloc(ui.count*24U+4U);','boxes=malloc(ui.count*24U+4U);baseline=malloc(ui.baseline_count*24U+4U);').replace('!boxes||!guard','!boxes||!baseline||!guard').replace('if(road_camera_draw(frame,live,result,boxes,&ui))','if(!readall(argv[4],baseline,ui.baseline_count*24U))return 5;\n if(road_camera_draw(frame,live,result,boxes,baseline,&ui))').replace('fopen(argv[5],','fopen(argv[6],').replace('free(boxes);','free(boxes);free(baseline);');p.write_text(s,encoding='ascii')
    for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','road_graph.h','road_camera_average.c','road_camera_io.c','road_enhance.c','road_retinex_c.c']:
        assert sha(src/n)==sha(OLD/'source'/n),n
    old=read(OLD/'arm_complete.json');obj=APP/'obj';obj.mkdir(exist_ok=rebuild);commands=[];logs=[]
    def run(cmd):
        commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    templates=[[v.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for v in cmd] for cmd in old['commands']]
    example=next(cmd for cmd in templates if any(Path(v).name=='road_retinex_c.c' for v in cmd))
    extra=[v.replace('road_retinex_c.c','road_vehicle_multiview.c').replace('road_retinex_c.o','road_vehicle_multiview.o') for v in example]
    for cmd in templates:
        if '-c' not in cmd:run(extra);cmd=cmd.copy();cmd.insert(cmd.index('-Wl,--start-group'),str(obj/'road_vehicle_multiview.o'))
        run(cmd)
    elf=APP/'road_detail.elf';raw=elf.read_bytes();assert b'ROAD_ACCURACY_READY V23' in raw
    phoff=struct.unpack_from('<I',raw,28)[0];ent,num=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(num):
        typ,off,va,pa,fs,mem,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    regions=list(old['regions'])+[[f'tile{i}',0x1A000000+i*0x60000,384000] for i in range(3)]+[[f'tiledecode{i}',0x1A120000+i*0x40000,226800] for i in range(3)]+[['baseline_boxes',0x1A200000,7200]]
    for i,(name,a,n) in enumerate(regions):
        assert a+n<=0x20000000
        for name2,b,l in regions[:i]:assert a+n<=b or b+l<=a,(name,name2)
        for b,e in loads:assert a+n<=b or e<=a
    common=(OLD/'camera_common.tcl').read_text().replace('!=22','!=23');common=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),common);(APP/'camera_common.tcl').write_text(common,encoding='ascii')
    start=(OLD/'start_idle.tcl').read_text().replace('==22','==23');(APP/'start_idle.tcl').write_text(start,encoding='ascii')
    host=APP/'host';host.mkdir(exist_ok=rebuild);gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    renderer=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(host/'render.exe')]
    p=subprocess.run(renderer,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
    write(APP/'arm_complete.json',dict(status='ABI23_FOUR_PASS_FIXED_PHOTO_COMPILED_NOT_DEPLOYED',version=23,commands=commands,renderer_command=renderer,regions=regions,elf_loads=loads,elf_sha256=sha(elf),bit_sha256=sha(APP/'display.bit'),weights_sha256=sha(APP/'runtime/weights.f32'),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},detector_weights_and_graph_unchanged=True,enhancement_same_as_abi22=True,ui_words=17,default_detail_mode=2,hardware_access=False,sd_written=False))
    print('ACCURACY_ABI23_COMPILED',sha(elf),flush=True)

if __name__=='__main__':main()
