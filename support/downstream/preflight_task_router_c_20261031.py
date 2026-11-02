"""Synthetic C feature/MLP consistency only; no accuracy acceptance."""
import os,shutil,subprocess,ctypes as ct
from pathlib import Path
import numpy as np
from road_task_router_common import *
from shadowlift_lab import words
def main():
    import torch
    out=ROOT/'controller_preflight';assert not out.exists();out.mkdir();source=Path(__file__).with_name('road_task_router.c');shutil.copy2(source,out/source.name)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse',str(out/source.name),'-lm','-o',str(out/'router.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    directory=os.add_dll_directory(str(gcc.parent));lib=ct.CDLL(str(out/'router.dll'));fp=ct.POINTER(ct.c_float);up=ct.POINTER(ct.c_uint32);lib.road_task_router_features.argtypes=[up,ct.c_uint,fp];lib.road_task_router_predict.argtypes=[fp,fp,fp,fp,fp,fp]
    torch.manual_seed(SEED);model=make_model().eval();state=model.state_dict();w=np.concatenate([state[k].numpy().reshape(-1) for k in ['0.weight','0.bias','3.weight','3.bias']]).astype(np.float32);assert len(w)==1155
    rng=np.random.default_rng(SEED);mean=rng.uniform(0,.1,68).astype(np.float32);scale=rng.uniform(.2,.5,68).astype(np.float32);cases=[np.full((240,400,3),k,np.uint8) for k in [0,1,8,16,24,48,49,96,114,128,200,254,255]]+[rng.integers(0,32+7*i,(240,400,3),np.uint8) for i in range(32)];proof=[]
    for i,a in enumerate(cases):
        raw=words(a).reshape(-1);before=raw.tobytes();f=np.full(70,np.float32(12345.25));prob=np.full(5,np.float32(12345.25));score=np.full(3,np.float32(12345.25));ptr=lambda x,offset=0:ct.cast(ct.c_void_p(x.ctypes.data+4*offset),fp)
        assert lib.road_task_router_features(raw.ctypes.data_as(up),96000,ptr(f,1))==0 and raw.tobytes()==before and np.all(f[[0,-1]]==np.float32(12345.25));ref=features(a);assert f[1:-1].tobytes()==ref.tobytes()
        assert lib.road_task_router_predict(ptr(f,1),ptr(w),ptr(mean),ptr(scale),ptr(prob,1),ptr(score,1))==0 and np.all(prob[[0,-1]]==np.float32(12345.25)) and np.all(score[[0,-1]]==np.float32(12345.25))
        with torch.inference_mode():expected=model(torch.from_numpy((ref-mean)/scale)[None]).softmax(1)[0].numpy()
        delta=float(np.abs(prob[1:-1]-expected).max());assert delta<=.00001;proof.append(dict(case=i,feature_byte_exact=True,prob_max_abs=delta))
    result=dict(status='SYNTHETIC_ROUTER_C_PREFLIGHT_PASSED_NOT_ACCURACY_PROOF',cases=len(cases),max_probability_abs=max(r['prob_max_abs'] for r in proof),features_byte_exact=True,source_immutable=True,canaries_intact=True,source_sha256=sha(out/source.name),dll_sha256=sha(out/'router.dll'),hardware_access=False,sd_written=False);write(out/'complete.json',result);print(result)
if __name__=='__main__':main()
