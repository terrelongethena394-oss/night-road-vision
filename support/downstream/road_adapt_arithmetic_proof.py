from pathlib import Path
import os,shutil,subprocess,time
import numpy as np
from road_adapt_common import ROOT,POLICIES,apply_policy,luma,write,sha
HERE=Path(__file__).resolve().parent
def main():
    while not ROOT.exists():time.sleep(.5)
    out=ROOT/'bounded_numeric_proof';out.mkdir(exist_ok=False)
    for name in ['road_bounded_luma.h','road_bounded_host.c']:shutil.copy2(HERE/name,out/name)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    p=subprocess.run([str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-static',str(out/'road_bounded_host.c'),'-o',str(out/'road_bounded_host.exe')],env=env,capture_output=True,text=True);assert p.returncode==0,p.stderr
    rng=np.random.default_rng(2026102627);raw=rng.integers(0,256,(100,100,3),dtype=np.uint8);net=rng.integers(0,256,raw.shape,dtype=np.uint8)
    raw[:2]=0;raw[2:4]=255;net[:1]=255;net[1:2]=0;raw.tofile(out/'raw.rgb');net.tofile(out/'net.rgb')
    count=0
    for policy in POLICIES:
        if policy['kind']!='bounded':continue
        result=out/(policy['name']+'.rgb')
        subprocess.run([str(out/'road_bounded_host.exe'),str(out/'raw.rgb'),str(out/'net.rgb'),'10000',str(policy['strength']),str(policy['cap']),str(policy['threshold']),str(result)],env=env,check=True)
        got=np.fromfile(result,np.uint8).reshape(raw.shape);want=apply_policy(raw,net,policy);assert np.array_equal(got,want)
        assert np.all(got>=raw) and np.array_equal(got[luma(raw)>=policy['threshold']],raw[luma(raw)>=policy['threshold']]);count+=1
    proof=dict(status='ALL_BOUNDED_LUMA_C_NUMPY_BYTES_EXACT',policies=count,pixels=count*10000,bytes=count*30000,header_sha256=sha(out/'road_bounded_luma.h'),
               max_product_bound=64*256*255,highlight_preservation=True,negative_net_delta_no_darkening=True,board_run=False)
    write(out/'complete.json',proof);print('BOUNDED_LUMA_ARITHMETIC_VERIFIED',proof,flush=True)
if __name__=='__main__':main()
