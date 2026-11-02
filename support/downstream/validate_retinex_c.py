"""Numerical/guard acceptance of the portable enhancement C port."""
from pathlib import Path
import ctypes as ct,datetime,json,hashlib,subprocess,os,shutil
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from road_retinex_project import enhance
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_arm_20261029_r1')
REF=Path('E:/FPGA_Enhance_Work/road_project_retinex_20261029_r3')
CORE_SOURCE=HERE/'road_retinex_c.c'
CORE_HEADER=HERE/'road_retinex_c.h'
REFERENCE_SOURCE=HERE/'road_retinex_project.py'
REFERENCE_PRESET='project_strong'
EXTRA_INPUTS=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ROOT.mkdir(exist_ok=True);attempt=ROOT/('c_check_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));attempt.mkdir()
    shutil.copy2(CORE_SOURCE,attempt/'road_retinex_c.c');shutil.copy2(CORE_HEADER,attempt/'road_retinex_c.h')
    protocol=dict(pixel_max_abs_allowed=1,mean_abs_allowed=.01,ssim_min=.99999,guards_required=True,input_immutable=True,reference_source_sha256=sha(REFERENCE_SOURCE),c_source_sha256=sha(CORE_SOURCE),output_is_rgb888=True,sd_written=False)
    (attempt/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    dll=attempt/'retinex.dll';cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-shared','-static-libgcc','-Wl,--export-all-symbols',str(attempt/'road_retinex_c.c'),'-lm','-o',str(dll)]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(attempt/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    lib=ct.CDLL(str(dll))
    class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
    ptr=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float)
    lib.road_retinex_c.argtypes=[ptr,ptr,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p];lib.road_retinex_c.restype=ct.c_int
    inputs=[(p.parent.name,np.array(Image.open(p).convert('RGB'))) for p in sorted((REF/'paired_regression').glob('*/raw.png'))]
    inputs +=[(p.parent.name,np.array(Image.open(p).convert('RGB'))) for p in sorted((REF/'showcase').glob('*/raw.png'))]
    inputs +=EXTRA_INPUTS
    for name,color in [('black',[0,0,0]),('white',[255,255,255]),('red',[255,0,0]),('blue',[0,0,255]),('green',[0,255,0]),('gray4',[4,4,4])]:inputs.append((name,np.tile(np.array(color,np.uint8),(240,400,1))))
    inputs.append(('random',np.random.default_rng(2026102901).integers(0,256,(240,400,3),dtype=np.uint8)))
    records=[]
    for name,a in inputs:
        z,es=enhance(a,REFERENCE_PRESET);v=a.astype(np.uint32);raw=np.ascontiguousarray(v[:,:,0]|v[:,:,1]<<8|v[:,:,2]<<16).reshape(-1);original=raw.copy()
        guard=0x5a5aa5a5;dest=np.full(96000+32,guard,dtype=np.uint32);work=np.full(17*96000+65536+32,guard,dtype=np.uint32)
        stats=Stats();out=dest[16:-16];buf=work[16:-16].view(np.float32)
        rc=lib.road_retinex_c(raw.ctypes.data_as(ptr),out.ctypes.data_as(ptr),96000,buf.ctypes.data_as(fp),ct.byref(stats),None,None)
        assert rc==0 and np.array_equal(raw,original)
        assert (dest[:16]==guard).all() and (dest[-16:]==guard).all() and (work[:16]==guard).all() and (work[-16:]==guard).all()
        b=np.stack([out&255,out>>8&255,out>>16&255],axis=1).astype(np.uint8).reshape(240,400,3)
        diff=np.abs(b.astype(np.int16)-z.astype(np.int16));ssim=float(structural_similarity(b,z,data_range=255,channel_axis=2))
        row=dict(name=name,max_abs=int(diff.max()),mean_abs=float(diff.mean()),ssim=ssim,stats={n:float(getattr(stats,n)) for n,_ in Stats._fields_})
        (attempt/(name+'.u32')).write_bytes(out.tobytes());Image.fromarray(b).save(attempt/(name+'.png'))
        records.append(row);print('RETINEX_C_CASE',name,row['max_abs'],row['mean_abs'],ssim,flush=True)
        assert row['max_abs']<=1 and row['mean_abs']<=.01 and ssim>=.99999,row
    result=dict(status=f'RETINEX_PORT_ALL{len(records)}_PIXEL_TOLERANCE_AND_GUARDS_PASS',attempt=str(attempt),cases=records,compiler_command=cmd,source_sha256=sha(CORE_SOURCE),reference_sha256=sha(REFERENCE_SOURCE),workspace_bytes=(17*96000+65536)*4,hardware_access=False,sd_written=False)
    (attempt/'complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(ROOT/'c_complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('RETINEX_C_ACCEPTANCE_COMPLETE',len(records),flush=True)
if __name__=='__main__':main()
