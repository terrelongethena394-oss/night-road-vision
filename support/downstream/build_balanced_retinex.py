"""Follow manual quality feedback with controlled integer blend, not retraining."""
from pathlib import Path
import json,shutil,ctypes as ct,subprocess,os,hashlib
import numpy as np
from PIL import Image
import build_retinex_arm as build

HERE=Path(__file__).resolve().parent
PREVIOUS=Path('E:/FPGA_Enhance_Work/road_retinex_arm_20261029_r1')
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_balanced_20261029_r1')
REF=Path('E:/FPGA_Enhance_Work/road_project_retinex_20261029_r3')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not ROOT.exists();ROOT.mkdir()
    write(PREVIOUS/'manual_display_status.json',dict(status='QUALITY_NOT_ACCEPTED',user_feedback='右边噪声有些明显，上下两边有点太糊了',stable_promotion_allowed=False,sd_written=False))
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_BALANCED_OUTPUTS',version=20,reason='Manual feedback: excessive noise and blur in sky/carhood; keep core and add raw-image texture blend.',default_strength=24,strength_denominator=48,formula='out=(raw*(48-cap)+strong*cap+24)//48 separately inRGB; retain original input, detector unchanged.',allowed_strengths=[0,12,24,36,48],blend_port_gate='Byte-exact at five strengths on all existing30 C fixtures',physical_gate='Same unchanged max1LSB/MAE.01/SSIM.99999 enhancement gate; detector byte-exact to actualABI18; display render byte-exact.',sd_written=False))
    for n in ['c_complete.json','actual_abi18_baseline.json']:shutil.copy2(PREVIOUS/n,ROOT/n)
    out=ROOT/'blend_host';out.mkdir();gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    dll=out/'blend.dll';cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DROAD_RETINEX_HOST_WORK','-I'+str(PREVIOUS/'firmware/source'),'-shared','-static-libgcc','-Wl,--export-all-symbols',str(HERE/'road_retinex_c.c'),str(HERE/'road_retinex_blend_wrapper.c'),'-lm','-o',str(dll)]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    lib=ct.CDLL(str(dll))
    class Stats(ct.Structure):_fields_=[(n,ct.c_uint32) for n in ['mean_in','mean_out','alpha','cap','changed','max_delta']]
    ptr=ct.POINTER(ct.c_uint32);lib.road_enhance.argtypes=[ptr,ptr,ct.c_uint32,ct.c_uint,ct.c_uint,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
    inputs=[(p.parent.name,np.array(Image.open(p).convert('RGB'))) for p in sorted((REF/'paired_regression').glob('*/raw.png'))]+[(p.parent.name,np.array(Image.open(p).convert('RGB'))) for p in sorted((REF/'showcase').glob('*/raw.png'))]
    for name,color in [('black',[0,0,0]),('white',[255,255,255]),('red',[255,0,0]),('blue',[0,0,255]),('green',[0,255,0]),('gray4',[4,4,4])]:inputs.append((name,np.tile(np.array(color,np.uint8),(240,400,1))))
    inputs.append(('random',np.random.default_rng(2026102901).integers(0,256,(240,400,3),dtype=np.uint8)))
    cdir=Path(read(ROOT/'c_complete.json')['attempt']);records=[]
    for name,a in inputs:
        b=a.astype(np.uint32);raw=np.ascontiguousarray(b[:,:,0]|b[:,:,1]<<8|b[:,:,2]<<16).reshape(-1);strong=np.fromfile(cdir/(name+'.u32'),'<u4');s=Stats()
        for cap in [0,12,24,36,48]:
            output=np.full(96032,0x5a5aa5a5,np.uint32);actual=output[16:-16]
            assert lib.road_enhance(raw.ctypes.data_as(ptr),actual.ctypes.data_as(ptr),96000,1,cap,ct.byref(s),None,None)==0
            aa=np.stack([raw&255,raw>>8&255,raw>>16&255],1);bb=np.stack([strong&255,strong>>8&255,strong>>16&255],1);mix=(aa*(48-cap)+bb*cap+24)//48;gold=(mix[:,0]|mix[:,1]<<8|mix[:,2]<<16).astype('<u4')
            assert np.array_equal(actual,gold) and (output[:16]==0x5a5aa5a5).all() and (output[-16:]==0x5a5aa5a5).all()
            records.append(dict(name=name,strength=cap,byte_exact=True))
        print('RETINEX_BLEND_HOST_PASS',name,flush=True)
    write(ROOT/'blend_complete.json',dict(status='ALL30_FIXTURES_AT5_STRENGTHS_BYTE_EXACT_AND_GUARDS_PASS',records=records,source_sha256=hashlib.sha256((HERE/'road_retinex_blend_wrapper.c').read_bytes()).hexdigest()))
    build.ROOT=ROOT;build.VERSION=20;build.DEFAULT_CAP=24;build.WRAPPER=HERE/'road_retinex_blend_wrapper.c';build.main()
if __name__=='__main__':main()
