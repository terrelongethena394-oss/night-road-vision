"""Frozen-checkpoint native arithmetic proof and once-only heldout evaluation."""
from pathlib import Path
import os,subprocess,json,gzip,time
import numpy as np
import torch
from recognition_upgrade_common import ROOT,BASE,OLD,SEED,UpgradeCNN,normalize_np,sha,write
from train_real_digit_cnn import IntegerCNN,conservative_bounds
from train_real_digit import backgrounds
HERE=Path(__file__).resolve().parent

def export_native(model_path,out):
    out.mkdir(exist_ok=True)
    state=torch.load(model_path,weights_only=True,map_location='cpu');q=IntegerCNN(state)
    bounds=conservative_bounds(q);np.savez(out/'integer_weights.npz',**q.s)
    # Bound every partial sum by |bias| + sum |product|, not only final signed interval.
    upper=np.array([255],np.int64);proof=[]
    for layer in ['conv1','conv2','fc1','fc2']:
        w=q.s[layer+'.weight'];b=q.s[layer+'.bias']
        if layer.startswith('conv'):
            ub=upper[None,:,None,None]
            absolute=(np.abs(w)*ub).sum((1,2,3))+np.abs(b)
            positive=(np.maximum(w,0)*ub).sum((1,2,3))+b
        else:
            if layer=='fc1':upper=np.repeat(upper,49)
            absolute=np.abs(w)@upper+np.abs(b);positive=np.maximum(w,0)@upper+b
        proof.append(dict(layer=layer,absolute_partial_sum_bound=int(absolute.max()),signed32_safe=bool(absolute.max()<2**31)))
        assert absolute.max()<2**39
        upper=np.clip((np.maximum(positive,0)+2048)>>12,0,1048575)
    def initializer(a):
        if a.ndim==1:return '{'+','.join(map(str,a.tolist()))+'}'
        return '{'+','.join(initializer(v) for v in a)+'}'
    text=['#ifndef CNN_WEIGHTS_H','#define CNN_WEIGHTS_H','#include <stdint.h>',f'#define CNN_HIDDEN {len(q.s["fc1.bias"])}']
    for k,v in q.s.items():
        typ='int32_t' if k.endswith('bias') else 'int16_t'
        shape=''.join('['+str(n)+']' for n in v.shape)
        text.append('static const '+typ+' CNN_'+k.upper().replace('.','_')+shape+'='+initializer(v)+';')
    text.append('#endif');(out/'cnn_weights.h').write_text('\n'.join(text),encoding='ascii')
    kernel=(HERE/'digit_arm_kernel.h').read_text()
    kernel=kernel.replace('hidden[32]','hidden[CNN_HIDDEN]').replace('o<32','o<CNN_HIDDEN').replace('j<32','j<CNN_HIDDEN')
    if not proof[2]['signed32_safe']:
        kernel=kernel.replace('int32_t acc;int64_t score,best;','int32_t acc;int64_t wide,score,best;')
        kernel=kernel.replace('acc=CNN_FC1_BIAS[o];','wide=CNN_FC1_BIAS[o];').replace('acc+=(int32_t)p2','wide+=(int64_t)p2').replace('hidden[o]=digit_activation(acc);','hidden[o]=digit_activation(wide);')
    # Convolution sums may stay32 only with a bound on every partial sum.
    if not all(r['signed32_safe'] for r in proof[:2]):
        kernel=kernel.replace('int32_t acc;','int64_t acc;').replace('(int32_t)gray','(int64_t)gray').replace('(int32_t)p1','(int64_t)p1')
    kernel=kernel.replace('26731-parameter','candidate').replace('Proven int32 conv1/conv2/fc1, int64 fc2.','Candidate-proven int32 accumulators where safe; otherwise int64. FC2 always int64.')
    (out/'digit_arm_kernel.h').write_text(kernel,encoding='ascii')
    (out/'digit_arm_host.c').write_text((HERE/'digit_arm_host.c').read_text(),encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
    env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-static',str(out/'digit_arm_host.c'),'-o',str(out/'digit_arm_host.exe')]
    r=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    data=np.load(BASE/'real_digit_training_20261025/data/train_board_gray.npz')
    x=np.concatenate([data['x'][:128],np.random.default_rng(SEED).integers(0,256,(16,28,28),dtype=np.uint8),np.zeros((1,28,28),np.uint8),np.full((1,28,28),255,np.uint8)])
    x=normalize_np(x);expected=q.infer(x)[1];actual=native(out/'digit_arm_host.exe',x,out,'arithmetic')
    assert np.array_equal(expected,actual)
    result=dict(status='NATIVE_C_NUMPY_ALL_LOGITS_EXACT',cases=len(x),logits=expected.size,model=str(model_path),model_sha256=sha(model_path),weights_header_sha256=sha(out/'cnn_weights.h'),integer_weights_sha256=sha(out/'integer_weights.npz'),kernel_sha256=sha(out/'digit_arm_kernel.h'),host_exe_sha256=sha(out/'digit_arm_host.exe'),accumulator_bounds=bounds,partial_sum_bounds=proof,hidden=len(q.s['fc1.bias']))
    write(out/'complete.json',result);return result

def native(exe,x,out,tag):
    ip=out/(tag+'.gray');op=out/(tag+'.scores');ip.write_bytes(np.asarray(x,np.uint8).tobytes())
    p=subprocess.run([str(exe),str(ip),str(op)],capture_output=True,text=True);assert p.returncode==0,p.stderr
    a=np.fromfile(op,dtype='<i8').reshape(-1,11);assert len(a)==len(x);return a

def main():
    import sys
    run=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'run01');freeze=json.loads((run/'frozen_candidate.json').read_text())
    model_path=Path(freeze['model']);assert sha(model_path)==freeze['sha256']
    out=run/'test';out.mkdir(exist_ok=True);assert not (out/'results.json').exists(),'Keep completed heldout results immutable'
    torch.set_num_threads(4);proof=export_native(model_path,run/'native')
    oldexe=BASE/'digit_arm_reference_i32_20261026/digit_arm_host.exe';newexe=run/'native/digit_arm_host.exe'
    model=UpgradeCNN(proof['hidden']);model.load_state_dict(torch.load(model_path,weights_only=True));model.eval()
    datasets={}
    a=np.load(BASE/'real_digit_training_20261025/data/official_test_board_gray.npz');datasets['svhn']=(a['x'],a['y'])
    for name in ['chars','fonts']:
        a=np.load(ROOT/'data'/f'{name}_test.npz');mask=a['y']<10;datasets[name]=(a['x'][mask],a['y'][mask])
    mr=BASE/'digit_recognition_20261023/mnist'
    mx=np.frombuffer(gzip.decompress((mr/'t10k-images-idx3-ubyte.gz').read_bytes()),np.uint8,offset=16).reshape(-1,28,28)
    my=np.frombuffer(gzip.decompress((mr/'t10k-labels-idx1-ubyte.gz').read_bytes()),np.uint8,offset=8)
    datasets['mnist']=(mx,my);datasets['background']=backgrounds(1000,SEED+90)
    results={};start=time.monotonic()
    for tag,(x,y) in datasets.items():
        xn=normalize_np(x);p={};scores={}
        for mode,exe,z in [('old_raw',oldexe,x),('old_normalized',oldexe,xn),('new_normalized',newexe,xn)]:
            s=native(exe,z,out,tag+'_'+mode);scores[mode]=s;p[mode]=s.argmax(1)
        with torch.inference_mode():
            fp=torch.cat([model(z).argmax(1) for z in (torch.from_numpy(xn.copy()).float()/256).split(512)]).numpy()
        result=dict(n=len(y),**{mode:dict(correct=int((v==y).sum()),accuracy=float((v==y).mean())) for mode,v in p.items()},float_integer_agreement=float((fp==p['new_normalized']).mean()),per_digit={str(k):dict(n=int((y==k).sum()),correct=int(((p['new_normalized']==y)&(y==k)).sum())) for k in sorted(set(y.tolist()))})
        results[tag]=result;np.savez_compressed(out/(tag+'_predictions.npz'),labels=y,float_predictions=fp,**p)
        print('HELDOUT',tag,json.dumps(result),round(time.monotonic()-start,1),flush=True)
    gates=dict(svhn=results['svhn']['new_normalized']['correct']>=22170,chars=results['chars']['new_normalized']['accuracy']>=max(.8,results['chars']['old_raw']['accuracy']+.05),fonts=results['fonts']['new_normalized']['accuracy']>=.9,mnist=results['mnist']['new_normalized']['accuracy']>=.95,background=results['background']['new_normalized']['accuracy']>=.95)
    revision=json.loads((run/'training_revision.json').read_text()) if (run/'training_revision.json').exists() else {}
    write(out/'results.json',dict(status='OFFLINE_ACCEPTED_PENDING_REGRESSION' if all(gates.values()) else 'HELDOUT_GATE_FAILED_DO_NOT_DEPLOY',accepted=all(gates.values()),gates=gates,results=results,model_sha256=sha(model_path),freeze_sha256=sha(run/'frozen_candidate.json'),evaluation_caveat=revision.get('evaluation_caveat','First frozen-candidate evaluation on these new external test splits; original SVHN test already used for legacy engineering acceptance.'),limitations=['Given ROI single-digit recognition, not scene detection or plate OCR.','Chars scene groups/font families heldout; SVHN source photos may not be independent per crop.','No enhancement benefit established by raw classifier accuracy.','No board or SD writes.']))
    print('OFFLINE_ACCEPTED',all(gates.values()),flush=True)
if __name__=='__main__':main()
