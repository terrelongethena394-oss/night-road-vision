"""Freeze-selected student: independent native arithmetic proof and heldout OCR."""
from pathlib import Path
import json,os,subprocess,time,shutil
import numpy as np
import torch,cv2
from plate_common import ROOT,SOURCE,SEED,CHARS,build_model,forward_per_image,decode,edit_distance,sha,write
from tiny_plate_model import TinyPlate
from tiny_plate_integer import IntegerPlate,normalized_np,ACT_BITS,ACT_MAX
from train_tiny_plate import gray_np,valid_word
HERE=Path(__file__).resolve().parent
OUT=ROOT/'tiny_student01'
def native(exe,images,folder,tag):
    ip=folder/(tag+'.gray');op=folder/(tag+'.i32');ip.write_bytes(images.astype(np.uint8).tobytes())
    r=subprocess.run([str(exe),str(ip),str(op)],capture_output=True,text=True);assert r.returncode==0,r.stderr
    z=np.fromfile(op,dtype='<i4').reshape(-1,68,24);assert len(z)==len(images);return z
def export(model_path):
    folder=OUT/'native';folder.mkdir(exist_ok=True);state=torch.load(model_path,weights_only=True,map_location='cpu');q=IntegerPlate(state)
    rows=['#ifndef PLATE_WEIGHTS_H','#define PLATE_WEIGHTS_H','#include <stdint.h>', '#define PLATE_LAYER_COUNT 9',f'#define PLATE_ACT_BITS {ACT_BITS}',f'#define PLATE_ACT_MAX {ACT_MAX}',
          'typedef struct { int cin,cout,hi,wi,ho,wo,kh,kw,sh,sw,ph,pw,groups,fraction,activation;const int16_t *weight;const int32_t *bias;} PlateLayer;']
    entries=[];proof=[];arrays={};macs=0
    for i,d in enumerate(q.layers):
        name='PLATE_L'+str(i);rows.append('static const int16_t '+name+'_W[]={' + ','.join(map(str,d['w'].ravel().tolist()))+'};')
        rows.append('static const int32_t '+name+'_B[]={' + ','.join(map(str,d['b'].tolist()))+'};')
        fields=[d[k] for k in ['cin','cout','hi','wi','ho','wo','kh','kw','sh','sw','ph','pw','groups','frac','activation']]
        entries.append('{'+','.join(str(int(x)) for x in fields)+','+name+'_W,'+name+'_B}')
        proof.append({k:v for k,v in d.items() if k not in ['w','b']});arrays[d['name']+'.weight']=d['w'];arrays[d['name']+'.bias']=d['b']
        macs+=d['cout']*d['ho']*d['wo']*(d['cin']//d['groups'])*d['kh']*d['kw']
    rows+=['static const PlateLayer PLATE_LAYERS[PLATE_LAYER_COUNT]={'+','.join(entries)+'};','#endif']
    (folder/'plate_weights.h').write_text('\n'.join(rows),encoding='ascii');np.savez(folder/'integer_weights.npz',**arrays)
    for name in ['plate_native_kernel.h','plate_native_host.c']:shutil.copy2(HERE/name,folder/name)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    r=subprocess.run([str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-static',str(folder/'plate_native_host.c'),'-o',str(folder/'plate_native_host.exe')],capture_output=True,text=True,env=env);(folder/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    d=np.load(ROOT/'data/train.npz');x=gray_np(d['x'][:8]);rng=np.random.default_rng(SEED)
    x=np.concatenate([x,np.zeros((1,32,96),np.uint8),np.full((1,32,96),255,np.uint8),rng.integers(0,256,(4,32,96),dtype=np.uint8)])
    expected=q.infer(x);got=native(folder/'plate_native_host.exe',x,folder,'arithmetic');assert np.array_equal(expected,got),'Native/NumPy integer mismatch'
    result=dict(status='PLATE_NATIVE_NUMPY_ALL_SCORES_EXACT',cases=len(x),scores=int(expected.size),model_sha256=sha(model_path),weights_header_sha256=sha(folder/'plate_weights.h'),kernel_sha256=sha(folder/'plate_native_kernel.h'),native_exe_sha256=sha(folder/'plate_native_host.exe'),integer_weights_sha256=sha(folder/'integer_weights.npz'),activation_bits=ACT_BITS,activation_cap=ACT_MAX,layers=proof,conv_macs=macs,head_score_fraction=ACT_BITS+q.layers[-1]['frac'])
    write(folder/'complete.json',result);print('NATIVE_PLATE_PROOF',len(x),expected.size,macs,flush=True);return result
@torch.inference_mode()
def teacher_predictions(model,images,device):
    out=[]
    for i in range(0,len(images),32):
        z=torch.from_numpy(((images[i:i+32].astype(np.float32)-127.5)/128).transpose(0,3,1,2).copy()).to(device)
        out.extend(decode(forward_per_image(model,z)))
    return out
def metrics(pred,truth):return dict(n=len(truth),correct=sum(a==b for a,b in zip(pred,truth)),full_plate_accuracy=float(np.mean([a==b for a,b in zip(pred,truth)])),character_error_rate=sum(edit_distance(a,b) for a,b in zip(pred,truth))/sum(map(len,truth)))
def main():
    freeze=json.loads((OUT/'frozen_candidate.json').read_text());model_path=Path(freeze['model']);assert sha(model_path)==freeze['sha256']
    folder=OUT/'test';folder.mkdir(exist_ok=True);assert not (folder/'results.json').exists()
    torch.set_num_threads(4);proof=export(model_path)
    device='cuda' if torch.cuda.is_available() else 'cpu';model=TinyPlate(len(CHARS)).to(device).eval();model.load_state_dict(torch.load(model_path,weights_only=True,map_location=device))
    teacher=build_model().to(device).eval();d=np.load(ROOT/'data/test.npz');raw=gray_np(d['x']);truth=d['texts'].tolist();results={};records=[]
    for gain in [1.,.25,.125]:
        gray=np.clip(np.floor(raw.astype(np.float32)*gain+.5),0,255).astype(np.uint8)
        scores=native(OUT/'native/plate_native_host.exe',gray,folder,'gain'+str(gain));pred=decode(scores)
        floating=[]
        with torch.inference_mode():
            for a in np.array_split(gray,max(1,(len(gray)+127)//128)):
                floating.extend(decode(model(torch.from_numpy(normalized_np(a).astype(np.float32)/(1<<ACT_BITS)).to(device))))
        teacher_images=np.clip(np.floor(d['teacher'].astype(np.float32)*gain+.5),0,255).astype(np.uint8);tp=teacher_predictions(teacher,teacher_images,device)
        report=dict(student_integer=metrics(pred,truth),student_float=metrics(floating,truth),teacher=metrics(tp,truth),float_integer_word_agreement=float(np.mean([a==b for a,b in zip(pred,floating)])),per_province={p:metrics([a for a,b in zip(pred,truth) if b[0]==p],[b for b in truth if b[0]==p]) for p in sorted({s[0] for s in truth})})
        results[str(gain)]=report;records.append(dict(gain=gain,truth=truth,integer_predictions=pred,float_predictions=floating,teacher_predictions=tp));print('PLATE_TEST',gain,json.dumps({k:v for k,v in report.items() if k!='per_province'}),flush=True)
    neg=np.load(ROOT/'negatives/test.npz')['x'];ns=native(OUT/'native/plate_native_host.exe',neg,folder,'nonplate');npred=decode(ns);far=float(np.mean([valid_word(s) for s in npred]));print('NONPLATE_TEST_FALSE_ACCEPT',far,flush=True)
    stress=None
    if (ROOT/'data/stress_test.npz').exists():
        s=np.load(ROOT/'data/stress_test.npz');p=decode(native(OUT/'native/plate_native_host.exe',gray_np(s['x']),folder,'stress'));stress=metrics(p,s['texts'].tolist())
        write(folder/'stress_cases.json',[dict(truth=t,prediction=q) for t,q in zip(s['texts'].tolist(),p)])
    gates=dict(normal=results['1.0']['student_integer']['full_plate_accuracy']>=max(.8,results['1.0']['teacher']['full_plate_accuracy']),dim=results['0.25']['student_integer']['full_plate_accuracy']>=.75,nonplate=far<=.01,quantization=all(r['float_integer_word_agreement']>=.97 for r in results.values()))
    write(folder/'all_plate_cases.json',records);write(folder/'nonplate_cases.json',dict(predictions=npred,valid=[valid_word(s) for s in npred]))
    write(folder/'results.json',dict(status='OFFLINE_PLATE_STUDENT_ACCEPTED' if all(gates.values()) else 'PLATE_TEST_GATE_FAILED_DO_NOT_DEPLOY',accepted=all(gates.values()),gates=gates,results=results,nonplate=dict(n=len(neg),false_acceptance=far),stress=stress,model_sha256=freeze['sha256'],proof=proof,limitations=['Given annotated plate crop, not whole-scene automatic detection.','Train/val/test plate IDs disjoint; upstream teacher pretraining overlap is unknown.','Mostly Anhui plates, province-specific results matter.','Synthetic gain not real paired night acquisition.','No new board deployment, latency measurement or claim that enhancement improves OCR yet.']))
    print('PLATE_STUDENT_OFFLINE_ACCEPTED',all(gates.values()),flush=True)
if __name__=='__main__':main()
