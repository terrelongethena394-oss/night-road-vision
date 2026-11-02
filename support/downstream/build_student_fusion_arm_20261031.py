"""ABI29 display-only fusion; preserve ABI28 raw detection and PLbit."""
from pathlib import Path
import shutil,subprocess,struct,os,re
from road_retinex_student_common import BASE,read,write,sha
from camera_snapshot_tools import fnv
STUDY=BASE/'road_student_fusion_20261031_r1'
ROOT=STUDY/'board_candidate';APP=ROOT/'firmware'
OLDROOT=BASE/'road_car_balanced_20261030_r1/board_candidate';OLD=OLDROOT/'firmware'

def main():
    assert read(STUDY/'complete.json')['quality_pass'];assert not ROOT.exists()
    write(STUDY/'visual_review.json',dict(status='ACCEPT_FOR_TEMPORARY_DISPLAY_EXPERIMENT',
      inspected=str(STUDY/'comparison.png'),findings='Three known roads have brighter dark pavement/building regions, retained prior edges/chroma, and less washout than the pure student. Sky/JPEG noise and original blur remain;not denoising/deblurring proof. No detection improvement attributed to enhancement.',
      paired_quality_scope='20previouslyused images,8referencegroups;diagnostic only',hardware_access=False,sd_written=False))
    ROOT.mkdir();APP.mkdir();shutil.copytree(OLD/'source',APP/'source');shutil.copytree(OLDROOT/'fixtures',ROOT/'fixtures');shutil.copytree(OLDROOT/'tools',ROOT/'tools')
    for n in ['obj','host','runtime']:(APP/n).mkdir()
    for n in ['display.bit','display.xsa','road_conv.bit','ps7_init.tcl','Xilinx.spec']:shutil.copy2(OLD/n,APP/n)
    for n in ['weights.f32','refiner_weights.f32']:shutil.copy2(OLD/'runtime'/n,APP/'runtime'/n)
    src=APP/'source'
    for n in ['road_student_restore.c','road_student_weights.h','road_retinex_c.h']:shutil.copy2(STUDY/'source'/n,src/n)
    shutil.copy2(STUDY/'source/road_student_fusion.c',src/'road_retinex_shadow.c')
    p=src/'road_enhance.c';s=p.read_text();s=s.replace('s->cap=48U;','s->cap=0U;');p.write_text(s,encoding='ascii')
    weightfnv=fnv((BASE/'road_retinex_student_20261031_r2/c_proof/weights.f32').read_bytes())
    p=src/'road_camera_main.c';s=p.read_text();assert s.count('m[M_VERSION]=28;')==1
    s=s.replace('m[M_VERSION]=28;','m[M_VERSION]=29;').replace('ROAD_BALANCED_CAR_READY V28','ROAD_STUDENT_FUSION_READY V29')
    s=s.replace('enhancement is ARM Retinex/patch filtering','enhancement is ARM Retinex/learned exposure fusion')
    anchor='m[199]=0x42414c32U;';assert s.count(anchor)==1
    s=s.replace(anchor,anchor+f'\n m[200]=0x53544631U;m[201]=411;m[202]={weightfnv}U;m[203]={32*96000+65536}U;m[204]=0x19000000U;m[205]=0x3f000000U;m[206]=9;m[207]=1;')
    p.write_text(s,encoding='ascii')
    p=src/'road_camera_draw.c';s=p.read_text().replace('"ENHANCED IMAGE"','"NEURAL ENHANCE"').replace('"RAW VS ENHANCED  CAR ONLY"','"LEARNED LIGHT  RAW DETECTION"').replace('"CUSTOM RETINEX / BRIGHT PROTECTED"','"RETINEX PLUS LEARNED EXPOSURE"');p.write_text(s,encoding='ascii')
    oldproof=read(OLD/'arm_complete.json');commands=[];logs=[]
    def run(cmd):
        commands.append(cmd);p=subprocess.run(cmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);(APP/'build.log').write_text('\n'.join(logs),encoding='utf-8');assert p.returncode==0,p.stderr
    templates=[[x.replace(str(OLD),str(APP)).replace(OLD.as_posix(),APP.as_posix()) for x in c] for c in oldproof['commands']]
    template=next(c for c in templates if any(Path(x).name=='road_vehicle_multiview.c' for x in c))
    for cmd in templates:
        if '-c' not in cmd:
            added=[x.replace('road_vehicle_multiview.c','road_student_restore.c').replace('road_vehicle_multiview.o','road_student_restore.o') for x in template];run(added)
            cmd=cmd.copy();cmd.insert(cmd.index('-Wl,--start-group'),str(APP/'obj/road_student_restore.o'))
        run(cmd)
    elf=APP/'road_detail.elf';data=elf.read_bytes();assert b'ROAD_STUDENT_FUSION_READY V29' in data
    loads=[];phoff=struct.unpack_from('<I',data,28)[0];entry,num=struct.unpack_from('<HH',data,42)
    for i in range(num):
        typ,off,va,pa,fs,mem,flags,align=struct.unpack_from('<8I',data,phoff+i*entry)
        if typ==1 and mem:assert 0x100000<=pa<pa+mem<=0x1000000;loads.append([pa,pa+mem])
    regions=[];found=False
    for name,address,size in oldproof['regions']:
        if address==0x19000000:size=(32*96000+65536)*4;found=True
        regions.append([name,address,size])
    assert found,'Need explicit enhancement workspace region'
    for i,(name,a,size) in enumerate(regions):
        assert a+size<=0x20000000
        for nn,b,nsize in regions[:i]:assert a+size<=b or b+nsize<=a,(name,nn)
        for b,e in loads:assert a+size<=b or e<=a
    for n in ['camera_common.tcl','start_idle.tcl']:
        s=(OLD/n).read_text().replace('!=28','!=29').replace('==28','==29');s=re.sub('elf_sha256=[0-9a-f]{64}','elf_sha256='+sha(elf),s);(APP/n).write_text(s,encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_camera_draw.c'),str(src/'road_camera_draw_host.c'),'-lm','-o',str(APP/'host/render.exe')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
    changed={'road_camera_main.c','road_camera_draw.c','road_enhance.c','road_retinex_c.h','road_retinex_shadow.c'}
    unchanged=[p.name for p in (OLD/'source').iterdir() if p.is_file() and p.name not in changed]
    for n in unchanged:assert sha(src/n)==sha(OLD/'source'/n),n
    proof=dict(oldproof,status='ABI29_LEARNED_DISPLAY_FUSION_COMPILED_REQUIRES_BOARD',version=29,commands=commands,regions=regions,elf_loads=loads,elf_sha256=sha(elf),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},
      unchanged_sources=unchanged,student_weight_fnv=weightfnv,student_parameters=411,student_weights_sha256=sha(BASE/'road_retinex_student_20261031_r2/c_proof/weights.f32'),
      enhancement_workspace_floats=32*96000+65536,quality_proof_sha256=sha(STUDY/'complete.json'),raw_detection_unchanged=True,sd_written=False)
    write(APP/'arm_complete.json',proof)
    tools=ROOT/'tools'
    (tools/'build_balanced_car_arm.py').write_text('from pathlib import Path\nROOT=Path('+repr(str(ROOT))+')\nAPP=ROOT/"firmware"\nSTUDY=Path('+repr(str(BASE/'road_car_balanced_20261030_r1'))+')\n',encoding='ascii')
    for name in ['balanced_board_tools.py','validate_balanced_board.py','verify_balanced_board.py','balanced_board_entry.py']:
        p=tools/name;s=p.read_text();s=s.replace('ABI28','ABI29').replace('m[1]==28','m[1]==29')
        if name=='validate_balanced_board.py':
            s=s.replace('from audit_bright_detector_20261030 import Enhancer','from student_display_runtime import Engine as Enhancer')
            s=s.replace('assert m[0]==0x524f4144',f'assert m[200:208]==(0x53544631,411,{weightfnv},{32*96000+65536},0x19000000,0x3f000000,9,1)\n assert m[0]==0x524f4144')
        if name=='balanced_board_tools.py':
            s=s.replace("old=Path('E:/FPGA_Enhance_Work/road_car_bright_20261030_r1/firmware')","old=Path('E:/FPGA_Enhance_Work/road_car_balanced_20261030_r1/board_candidate/firmware')").replace('PREVIOUS_ABI27','PREVIOUS_ABI28').replace('restore_ABI27','restore_ABI28')
            s=s.replace('set i 0} {$i<1800}','set i 0} {$i<3000}')
        if name=='verify_balanced_board.py':
            s=s.replace("'board_20261030_'","'board_20261031_'").replace('restore ABI27','restore ABI28')
        p.write_text(s,encoding='utf-8')
    runtime='''from pathlib import Path
import ctypes as ct,os,json,hashlib
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_student_fusion_20261031_r1'
class Engine:
 def __init__(self):
  p=ROOT/'host/fusion.dll';proof=json.loads((ROOT/'complete.json').read_text(encoding='utf-8'));assert hashlib.sha256(p.read_bytes()).hexdigest()==proof['dll_sha256']
  self.directory=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(p))
  class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
  self.Stats=Stats;self.up=ct.POINTER(ct.c_uint32);self.fp=ct.POINTER(ct.c_float);self.work=np.empty(32*96000+65536,np.float32)
  self.lib.road_retinex_c.argtypes=[self.up,self.up,ct.c_uint,self.fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 def run(self,a):
  v=a.astype(np.uint32);r=np.ascontiguousarray(v[:,:,0]|v[:,:,1]<<8|v[:,:,2]<<16).reshape(-1);out=np.empty_like(r);s=self.Stats()
  assert self.lib.road_retinex_c(r.ctypes.data_as(self.up),out.ctypes.data_as(self.up),96000,self.work.ctypes.data_as(self.fp),ct.byref(s),None,None)==0
  return np.stack([out&255,out>>8&255,out>>16&255],1).astype(np.uint8).reshape(240,400,3)
'''
    (tools/'student_display_runtime.py').write_text(runtime,encoding='ascii')
    deps=read(OLDROOT/'runtime_dependencies.json')
    deps.update({str(p):sha(p) for p in tools.glob('*.py')});deps[str(STUDY/'host/fusion.dll')]=sha(STUDY/'host/fusion.dll');deps[str(STUDY/'complete.json')]=sha(STUDY/'complete.json')
    write(ROOT/'runtime_dependencies.json',deps)
    shutil.copy2(__file__,ROOT/Path(__file__).name)
    print('STUDENT_FUSION_ABI29_COMPILED',sha(elf),'work',hex(0x19000000+(32*96000+65536)*4),'studentfnv',weightfnv,flush=True)
if __name__=='__main__':main()
