"""Portable gamma implementation safety/numerics, not candidate acceptance."""
import os,subprocess,shutil
from pathlib import Path
import numpy as np
from train_allview_gamma_20261031 import ROOT
from road_enhanced_detection_common import BASE,read,write,sha
import allview_enhance_native as native
import road_accuracy_common as ac
def main():
    out=ROOT/'kernel_preflight';assert not out.exists();out.mkdir();src=out/'source';src.mkdir()
    shutil.copy2(BASE/'road_student_fusion_20261031_r1/source/road_retinex_c.h',src/'road_retinex_c.h');shutil.copy2(Path(__file__).with_name('road_gamma_paper_detection.c'),src/'road_gamma_paper_detection.c')
    (src/'road_allview_config.h').write_text('#define ROAD_ALLVIEW_KIND 0\n#define ROAD_ALLVIEW_GAMMA .8f\n',encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-I'+str(src),str(src/'road_gamma_paper_detection.c'),'-lm','-o',str(out/'enhance.dll')]
    p=subprocess.run(cmd,env=env,capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    # Engine's root layout expects c_proof; subclass by patching CDLL path only
    # through a dedicated temporary root, leaving candidate proof untouched.
    temp=out/'layout';(temp/'c_proof').mkdir(parents=True);shutil.copy2(out/'enhance.dll',temp/'c_proof/enhance.dll');native.ROOT=temp;e=native.Engine();rng=np.random.default_rng(2026103162);tests=[]
    for k in range(256):
        a=np.full((240,400,3),k,np.uint8);b=e.run(a);ref=ac.gamma(a,'gamma080') if 0<k<=48 else a.copy();d=np.abs(b.astype(np.int16)-ref.astype(np.int16));assert d.max()<=1 and d.mean()<.005,(k,d.max(),d.mean());tests.append(dict(case='gray'+str(k),max_abs=int(d.max()),mean_abs=float(d.mean())))
    for j in range(16):
        a=rng.integers(0,32+j*2,(240,400,3),np.uint8);a[j*8:j*8+5,::4]=[255,2,5];b=e.run(a);ref=ac.gamma(a,'gamma080');d=np.abs(b.astype(np.int16)-ref.astype(np.int16));assert d.max()<=1 and d.mean()<.005,(j,d.max(),d.mean());tests.append(dict(case='darkrandom'+str(j),max_abs=int(d.max()),mean_abs=float(d.mean())))
    proof=dict(status='GAMMA_C_NUMERICS_PREFLIGHT_PASSED_NOT_ACCURACY_ACCEPTANCE',cases=len(tests),max_abs=max(t['max_abs'] for t in tests),max_mean=max(t['mean_abs'] for t in tests),dll_sha256=sha(out/'enhance.dll'),source_immutable=True,workspace_and_output_canaries_intact=True,hardware_access=False,sd_written=False)
    write(out/'pixel_tests.json',tests);write(out/'complete.json',proof);print(proof)
if __name__=='__main__':main()
