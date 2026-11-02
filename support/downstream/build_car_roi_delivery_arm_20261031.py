"""Compile independent ABI30 candidate; programming requires accepted fresh result."""
from pathlib import Path
import shutil,subprocess,struct,os,re
from car_roi_delivery_common import *
from camera_snapshot_tools import fnv
BOARD=ROOT/'board_candidate';APP=BOARD/'firmware';OLDROOT=BASE/'road_student_fusion_20261031_r1/board_candidate';OLD=OLDROOT/'firmware'

def main():
    assert read(ROOT/'c_proof/complete.json')['qualified'];assert not BOARD.exists();BOARD.mkdir();APP.mkdir();shutil.copytree(OLD/'source',APP/'source');shutil.copytree(OLDROOT/'fixtures',BOARD/'fixtures')
    for n in ['obj','host','runtime']:(APP/n).mkdir()
    for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
    for n in ['weights.f32','refiner_weights.f32']:shutil.copy2(OLD/'runtime'/n,APP/'runtime'/n)
    shutil.copy2(ROOT/'export/weights.f32',APP/'runtime/roi_weights.f32');weightfnv=fnv((APP/'runtime/roi_weights.f32').read_bytes());src=APP/'source'
    for n in ['road_native_car_roi.c','road_car_roi_verify.c','road_roi_verify_hw.c','road_roi_verify_hw.h']:shutil.copy2(Path(__file__).with_name(n),src/n)
    (src/'roi_model_config.h').write_text('#define ROI_MODEL_FNV '+str(weightfnv)+'U\n',encoding='ascii')
    p=src/'road_car_pair_post.c';s=p.read_text();assert s.count('all[i].cls==1&&all[i].score>=.25f')==1;s=s.replace('all[i].cls==1&&all[i].score>=.25f','all[i].cls==1');p.write_text(s,encoding='ascii')
    p=src/'road_balanced_extra.c';s=p.read_text();assert s.count('int v,i,n,kept,')==1;s=s.replace('int v,i,n,kept,','int v,i,n,');a=s.index(' kept=0;for(i=0;i<n;i++)if(out[i].score>=.25f)');b=s.index(' m[190]=3;',a);s=s[:a]+s[b:];s=s.replace('return kept;','return n;');p.write_text(s,encoding='ascii')
    p=src/'road_camera_main.c';s=p.read_text();s=s.replace('#define NEW_WEIGHT 0x1B000000U','#include "road_roi_verify_hw.h"\n#include "roi_model_config.h"\n#define NEW_WEIGHT 0x1B000000U')
    s=s.replace('m[M_VERSION]=29;','m[M_VERSION]=30;').replace('ROAD_STUDENT_FUSION_READY V29','ROAD_NATIVE_ROI_READY V30');s=s.replace('enhancement is ARM Retinex/learned exposure fusion; convolution acceleration remains in PL.','enhancement is display-only ARM fusion; RAW native ROI verification uses shared PL convolutions.')
    a=s.index(' {unsigned calls0=0,calls1=0,v;');b=s.index('\n boxes(RC_BOX400',a)
    block=r''' {unsigned calls0=0,calls1=0,calls_roi=0,v,visible=0;uint64_t net0=0,net1=0,net_roi=0,total=0;XTime t0,t1,t2,t3;int base_count,full_count;
  XTime_GetTime(&t0);count=road_car_pair_model((const float *)RC_WEIGHT,1,pair_cars,&calls0,&net0);if(count<0||calls0!=204U)fatal(50);
  for(v=0;v<4;v++){uint32_t source=v?RVM_DECODE(v-1):RC_FULL_DECODE,dest=0x1B800000U+v*0x40000U;memcpy((void *)dest,(const void *)source,ROAD_CANDIDATES*9U*4U);Xil_DCacheFlushRange(dest,ROAD_CANDIDATES*9U*4U);}
  for(v=0;v<96000;v++){uint32_t q=((const uint32_t *)RC_INPUT)[v];total+=54U*(q&255U)+183U*((q>>8)&255U)+19U*((q>>16)&255U);}
  m[189]=total<=48ULL*256ULL*96000ULL?1U:0U;XTime_GetTime(&t1);
  if(m[189]){count=road_balanced_extra((const float *)RC_WEIGHT,(const uint8_t *)RVM_SOURCE800,pair_cars,count,(RoadBox *)RC_KEEP,&calls1,&net1);if(count<0||calls1!=153U)fatal(51);}
  else{memcpy((void *)RC_KEEP,pair_cars,(unsigned)count*sizeof(RoadBox));m[190]=m[194]=0;memset((void *)BAL_REFINER_PRED,0,900U*5U*4U);Xil_DCacheFlushRange(BAL_REFINER_PRED,900U*5U*4U);for(v=0;v<3;v++)m[180+v]=m[183+v]=0;}
  XTime_GetTime(&t2);base_count=count;memcpy((void *)ROI_BASE_STRUCT,(const void *)RC_KEEP,(unsigned)count*sizeof(RoadBox));boxes(ROI_BASE_FLOAT,(const RoadBox *)ROI_BASE_STRUCT,count);m[212]=(unsigned)count;
  for(v=0;v<(unsigned)count;v++)if(((RoadBox *)ROI_BASE_STRUCT)[v].score>=.25f){boxes(RVM_BASELINE+visible*24U,(const RoadBox *)ROI_BASE_STRUCT+v,1);visible++;}
  rvm_baseline_count=visible;m[213]=visible;Xil_DCacheFlushRange(RVM_BASELINE,visible*24U);
  if(m[189]){count=road_roi_verify_live((const float *)ROI_VERIFY_WEIGHT,(const uint8_t *)RVM_SOURCE800,(const RoadBox *)ROI_BASE_STRUCT,base_count,(RoadBox *)RC_KEEP,&calls_roi,&net_roi);if(count<0||calls_roi!=51U*m[209])fatal(60);}
  else{m[209]=0;for(v=0;v<8;v++)m[220+v]=m[228+v]=m[236+v]=m[244+v]=m[252+v]=0;boxes(ROI_FINAL_FLOAT,(const RoadBox *)RC_KEEP,count);memset((void *)ROI_PLAN_DATA,0,128U);memset((void *)ROI_LOCAL_BOXES,0,8U*300U*6U*4U);}
  full_count=count;m[214]=(unsigned)count;visible=0;for(v=0;v<(unsigned)count;v++)if(((RoadBox *)RC_KEEP)[v].score>=.25f)((RoadBox *)RC_KEEP)[visible++]=((RoadBox *)RC_KEEP)[v];count=(int)visible;
  (void)full_count;XTime_GetTime(&t3);m[104]=calls0+calls1+calls_roi;m[169]=calls0;m[170]=calls1;m[171]=rvm_baseline_count;m[172]=(unsigned)count;m[163]=1;m[215]=calls_roi;
  ticks(165,t1-t0);ticks(167,t2-t1);ticks(216,t3-t2);network_ticks=net0+net1+net_roi;m[M_WEIGHT]=RC_WEIGHT;m[M_WEIGHT_FNV]=m[161];
  m[142]=rvm_baseline_count;m[143]=RVM_BASELINE;m[99]=2;m[102]=(unsigned)count;result_detail=2;p1=p0;
  Xil_DCacheFlushRange(ROI_BASE_STRUCT,300U*sizeof(RoadBox));Xil_DCacheFlushRange(ROI_BASE_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_FINAL_FLOAT,300U*6U*4U);Xil_DCacheFlushRange(ROI_LOCAL_BOXES,8U*300U*6U*4U);Xil_DCacheFlushRange(ROI_PLAN_DATA,128U);
 }'''
    s=s[:a]+block+s[b:]
    anchor='m[207]=1;';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n m[208]=0x524f4931U;m[211]=ROI_VERIFY_WEIGHT;m[260]=ROI_BASE_FLOAT;m[261]=ROI_FINAL_FLOAT;m[262]=ROI_LOCAL_BOXES;m[263]=ROI_PLAN_DATA;m[264]=ROI_BASE_STRUCT;')
    anchor='m[M_WEIGHT_READY]=0x57475453U;';assert s.count(anchor)==1;s=s.replace(anchor,'Xil_DCacheInvalidateRange(ROI_VERIFY_WEIGHT,ROAD_WEIGHT_FLOATS*4U);m[210]=hash((const void *)ROI_VERIFY_WEIGHT,ROAD_WEIGHT_FLOATS*4U);if(m[210]!=ROI_MODEL_FNV){m[M_ERROR]=61;m[M_COMMAND]=0;barrier();continue;}\n    '+anchor)
    p.write_text(s,encoding='ascii')
    p=src/'road_camera_draw.c';s=p.read_text();s=s.replace('(u->has_result&&view?result:live)','live');s=s.replace('if(u->has_result){v=result[y*400+x];','if(u->has_result){v=(view?live:result)[y*400+x];');s=s.replace('"BASE 4 VIEWS"','"STABLE RAW7"').replace('"ADAPTIVE DETAIL"','"ROI VERIFIED"').replace('"SAME FRAME  RAW DETECTION"','"SAME RAW INPUT  ROI VERIFY"').replace('"BALANCED CAR EXPERIMENT"','"RAW7 VS RAW7 PLUS ROI"').replace('"LEARNED LIGHT  RAW DETECTION"','"LEARNED LIGHT  RAW ROI DET"');p.write_text(s,encoding='ascii')
    oldproof=read(OLD/'arm_complete.json');templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in cmd] for cmd in oldproof['commands']];template=next(c for c in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in c));commands=[];logs=[]
    def run(cmd):
        commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    additions=[]
    for n in ['road_native_car_roi','road_car_roi_verify','road_roi_verify_hw']:
        cmd=[x.replace('road_vehicle_multiview.c',n+'.c').replace('road_vehicle_multiview.o',n+'.o') for x in template];run(cmd);additions.append(str(APP/'obj'/(n+'.o')))
    for cmd in templates:
        if '-c' not in cmd:
            cmd=cmd.copy();at=cmd.index('-Wl,--start-group');cmd[at:at]=additions
        run(cmd)
    elf=APP/'road_detail.elf';data=elf.read_bytes();assert b'ROAD_NATIVE_ROI_READY V30' in data;loads=[];phoff=struct.unpack_from('<I',data,28)[0];entry,num=struct.unpack_from('<HH',data,42)
    for i in range(num):
        typ,off,va,pa,fs,mem,flags,align=struct.unpack_from('<8I',data,phoff+i*entry)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    regions=[list(r) for r in oldproof['regions']]
    for r in regions:
        if r[0]=='ui':r[2]=68
    regions += [['native_roi_inputs',0x1D000000,8*0x60000],['native_roi_decodes',0x1D300000,8*0x40000],['native_roi_locals',0x1D500000,8*300*6*4],['native_roi_base',0x1D510000,300*6*4],['native_roi_final',0x1D520000,300*6*4],['native_roi_plan',0x1D530000,128],['native_roi_base_struct',0x1D540000,300*28]]
    for i,(name,a,size) in enumerate(regions):
        assert a+size<=0x20000000
        for nn,b,nsize in regions[:i]:assert a+size<=b or b+nsize<=a,(name,nn)
        for b,e in loads:assert a+size<=b or e<=a
    (APP/'camera_common.tcl').write_text('set root [file dirname [file normalize [info script]]]\n'+(OLD/'camera_common.tcl').read_text().split('proc word',1)[1].split('proc rc_test',1)[0].join(['proc word','']).replace('!=29','!=30'),encoding='ascii')
    s=(OLD/'start_idle.tcl').read_text().replace('==29','==30');anchor='dow -data $root/runtime/refiner_weights.f32 0x1C200000';assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n dow -data $root/runtime/roi_weights.f32 0x1B000000');(APP/'start_idle.tcl').write_text(s,encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host/render.exe')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
    proof=dict(oldproof,status='ABI30_NATIVE_ROI_COMPILED_NOT_YET_PROGRAMMED',version=30,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},roi_weight_fnv=weightfnv,roi_weights_sha256=sha(APP/'runtime/roi_weights.f32'),roi_checkpoint_sha256=sha(CHECKPOINT),raw_inference=True,enhancement_display_unchanged=True,pl_bit_unchanged=sha(APP/'display.bit')==oldproof['bit_sha256'],c_proof_sha256=sha(ROOT/'c_proof/complete.json'),physical_programmed=False,sd_written=False);write(APP/'arm_complete.json',proof);shutil.copy2(__file__,BOARD/Path(__file__).name);print('NATIVE_ROI_ABI30_COMPILED',sha(elf),weightfnv,flush=True)
if __name__=='__main__':main()
