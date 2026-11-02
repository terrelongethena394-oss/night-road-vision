"""Only after development qualification:freeze actual C task-enhancement."""
import os,ctypes as ct,shutil,subprocess
import numpy as np
from road_task_gate_common import *
from shadowlift_lab import words,unpack

class Engine:
    def __init__(self):
        self.path=os.add_dll_directory('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin');self.lib=ct.CDLL(str(ROOT/'c_proof/task.dll'))
        class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
        self.Stats=Stats;self.up=ct.POINTER(ct.c_uint32);self.fp=ct.POINTER(ct.c_float);self.work=np.empty(32*96000+65540,np.float32);self.work.view(np.uint32)[-4:]=0x7fcabcde
        self.lib.road_retinex_c.argtypes=[self.up,self.up,ct.c_uint,self.fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
    def run(self,a):
        r=words(a).reshape(-1).copy();before=r.copy();z=np.empty(96004,np.uint32);z[-4:]=0xdeadbeef;s=self.Stats()
        assert self.lib.road_retinex_c(r.ctypes.data_as(self.up),z.ctypes.data_as(self.up),96000,self.work.ctypes.data_as(self.fp),ct.byref(s),None,None)==0
        assert np.array_equal(r,before) and np.all(z[-4:]==0xdeadbeef) and np.all(self.work.view(np.uint32)[-4:]==0x7fcabcde)
        return unpack(z[:96000]).reshape(240,400,3)

def main():
    import torch
    selection=read(ROOT/'selected.json');assert selection['qualified'];assert not (ROOT/'c_proof').exists();out=ROOT/'c_proof';out.mkdir();src=out/'source';src.mkdir()
    chosen=selection['chosen']['name'];kind=int(chosen.startswith('gate'));config='#ifndef ROAD_TASK_GATE_CONFIG_H\n#define ROAD_TASK_GATE_CONFIG_H\n#define ROAD_TASK_GATE_KIND '+str(kind)+'\n'
    net=None
    if kind:
        ck=ROOT/'frozen'/('epoch'+chosen[4:])/'model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256'];state=torch.load(ck,map_location='cpu',weights_only=True)
        net=make_model().cuda().eval();net.load_state_dict(state);keys=['first.weight','first.bias','depth.weight','depth.bias','head.weight','head.bias'];w=np.concatenate([state[k].numpy().reshape(-1) for k in keys]).astype('<f4');assert len(w)==153;w.tofile(out/'weights.f32')
        config+='static const float road_task_gate_weights[153]={'+','.join(float(v).hex()+'f' for v in w)+'};\n'
    else:config+='#define ROAD_TASK_GATE_K '+chosen.replace('uniform','')+'U\n'
    (src/'road_task_gate_config.h').write_text(config+'#endif\n',encoding='ascii')
    old=BASE/'road_student_fusion_20261031_r1/source'
    for name in ['road_retinex_c.c','road_retinex_c.h','road_shadowlift.c','road_shadowlift.h','road_student_restore.c','road_student_weights.h']:shutil.copy2(old/name,src/name)
    s=(old/'road_student_fusion.c').read_text();assert s.count('int road_retinex_c(')==1
    (src/'road_task_bright.c').write_text(s.replace('int road_retinex_c(','int road_fusion_bright('),encoding='ascii')
    shutil.copy2(Path(__file__).with_name('road_detection_task_gate.c'),src/'road_detection_task_gate.c')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-I'+str(src),*[str(src/n) for n in ['road_retinex_c.c','road_shadowlift.c','road_student_restore.c','road_task_bright.c','road_detection_task_gate.c']],'-lm','-o',str(out/'task.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    from prove_student_fusion_20261031 import Engine as Bright
    from road_retinex_project import illumination
    engine=Engine();bright=Bright();tests=[]
    sources=read(BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources'];cases=[('gray'+str(k),np.full((240,400,3),k,np.uint8)) for k in [0,1,16,47,48,49,96,255]]
    cases +=[(s['name'],unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3)) for s in sources]
    for name,a in cases:
        b=bright.run(a);total=int((a.astype(np.uint64)*np.array([54,183,19],np.uint64)).sum())
        if total==0 or total>48*256*96000:expected=a
        elif kind:
            with torch.inference_mode():z,_=net(torch.from_numpy(a.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(b.transpose(2,0,1).copy()).cuda().float()[None]/255,torch.from_numpy(illumination(a)).cuda()[None,None])
            expected=np.floor(z[0].permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8)
        else:
            k=int(chosen.replace('uniform',''));expected=((a.astype(np.uint32)*(20-k)+b.astype(np.uint32)*k+10)//20).astype(np.uint8)
        actual=engine.run(a);d=np.abs(actual.astype(np.int16)-expected.astype(np.int16));assert d.max()<=1 and d.mean()<.005,(name,d.max(),d.mean())
        tests.append(dict(name=name,max_abs=int(d.max()),mean_abs=float(d.mean())))
    write(out/'complete.json',dict(status='TASK_ENHANCEMENT_C_KERNEL_NUMERICALLY_PROVED',chosen=chosen,parameters=153 if kind else 0,tests=tests,source_sha256={p.name:sha(p) for p in src.iterdir()},dll_sha256=sha(out/'task.dll'),selection_sha256=sha(ROOT/'selected.json'),commands=[cmd],hardware_access=False,sd_written=False))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('TASK_GATE_C_KERNEL_PROVED',chosen,flush=True)
if __name__=='__main__':main()
