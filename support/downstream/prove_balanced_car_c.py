"""Port selected learned refiner and fusion to portable C before fresh inference."""
from pathlib import Path
import ctypes as ct,os,shutil,subprocess
import numpy as np
from study_balanced_car_20261030 import ROOT,gates
from car_box_refine_common import BASE,ROOT as REF,make_model,patch,read,write,sha
from evaluate_car_patch_verifier import cohorts
from evaluate_car_boxrefine import eligible,fuse_refined
from road_classwise_native import Box
from road_numpy_eval import evaluate

class RefinerC:
 def __init__(self):
  if (ROOT/'c_complete.json').exists():assert sha(ROOT/'c_proof/refiner.dll')==read(ROOT/'c_complete.json')['dll_sha256']
  assert sha(ROOT/'export/weights.f32')==read(ROOT/'export/complete.json')['weights_sha256']
  self.lib=ct.CDLL(str(ROOT/'c_proof/refiner.dll'));self.fp=ct.POINTER(ct.c_float);self.bp=ct.POINTER(Box);self.up=ct.POINTER(ct.c_ubyte)
  self.weights=np.fromfile(ROOT/'export/weights.f32','<f4');assert len(self.weights)==17549
  self.fn=self.lib.road_box_refiner;self.fn.argtypes=[self.fp,self.up,self.fp,self.fp,self.fp];self.fn.restype=ct.c_int
  self.features=self.lib.road_patch_features;self.features.argtypes=[self.up,self.fp,self.up,self.fp];self.features.restype=ct.c_int
  self.post=self.lib.road_car_refined_zoom;self.post.argtypes=[self.bp,ct.c_int,self.bp,ct.POINTER(ct.c_int),ct.c_float,self.fp,ct.c_float,ct.c_float,ct.c_float,self.bp,ct.c_int];self.post.restype=ct.c_int
  self.work=np.empty(6562,np.float32)
 def begin(self,sensor):self.source=np.ascontiguousarray(sensor[:,:,::-1]);self.before=self.source.tobytes()
 def end(self):assert self.source.tobytes()==self.before
 def crop(self,b):
  box=np.asarray(b,np.float32);pixels=np.full(3074,91,np.uint8);meta=np.full(8,np.float32(12345.25))
  assert self.features(self.source.ctypes.data_as(self.up),box.ctypes.data_as(self.fp),ct.cast(ct.c_void_p(pixels.ctypes.data+1),self.up),ct.cast(ct.c_void_p(meta.ctypes.data+4),self.fp))==0
  assert pixels[0]==pixels[-1]==91 and np.all(meta[[0,-1]]==np.float32(12345.25))
  return pixels[1:-1].reshape(32,32,3).copy(),meta[1:-1].copy()
 def predict(self,image,meta):
  a=np.ascontiguousarray(image,np.uint8);m=np.ascontiguousarray(meta,np.float32);result=np.full(7,np.float32(12345.25));self.work[[0,-1]]=np.float32(12345.25)
  assert self.fn(self.weights.ctypes.data_as(self.fp),a.ctypes.data_as(self.up),m.ctypes.data_as(self.fp),ct.cast(ct.c_void_p(self.work.ctypes.data+4),self.fp),ct.cast(ct.c_void_p(result.ctypes.data+4),self.fp))==0
  assert np.all(self.work[[0,-1]]==np.float32(12345.25)) and np.all(result[[0,-1]]==np.float32(12345.25)) and np.isfinite(result).all()
  return result[1:-1].copy()
 def fuse(self,raw,local,mapped_outputs,params):
  a=(Box*300)();b=(Box*900)();out=(Box*302)();pred=np.zeros((900,5),np.float32)
  out[0].order=out[301].order=0x12345678
  for i,p in enumerate(raw):a[i]=Box(*map(float,p[:5]),int(p[5]),i)
  for t,pp in enumerate(local):
   k=0
   for i,p in enumerate(pp):
    b[t*300+i]=Box(*map(float,p[:5]),int(p[5]),i)
    if int(p[5])==1 and p[0]>1 and p[1]>1 and p[2]<399 and p[3]<239:
     pred[t*300+i]=mapped_outputs[t][k];k+=1
   assert k==len(mapped_outputs[t])
  aa=bytes(a);bb=bytes(b);ptr=ct.cast(ct.byref(out,ct.sizeof(Box)),self.bp)
  n=self.post(a,len(raw),b,(ct.c_int*3)(*[len(p) for p in local]),.65,pred.ctypes.data_as(self.fp),params['strength'],params['cap'],params['class_gate'],ptr,300)
  assert 0<=n<=300 and bytes(a)==aa and bytes(b)==bb and out[0].order==out[301].order==0x12345678
  return np.array([[out[i+1].x1,out[i+1].y1,out[i+1].x2,out[i+1].y2,out[i+1].score,out[i+1].cls] for i in range(n)],np.float32).reshape(-1,6)

def locals_for(key):
 if key=='reused320':return {r['name']:r['local'] for r in read(BASE/'road_car_zoom_20261030_r1/zoom_predictions.json')}
 p=BASE/'road_car_zoom_20261030_r1/confirmation';local=[{r['name']:r['detections'] for r in read(p/f'zoom{i}_actual_c.json')} for i in range(3)]
 return {name:[local[i][name] for i in range(3)] for name in local[0]}

def main():
 selected=read(ROOT/'selected.json');assert selected['qualified'] and selected['chosen']['family']=='box_refiner'
 chosen=selected['chosen']['source'];ck=Path(chosen['checkpoint']);assert sha(ck)==chosen['sha256']
 import torch
 saved=torch.load(ck,map_location='cpu',weights_only=False);model=make_model().float().cuda().eval();model.load_state_dict(saved['state_dict'])
 export=ROOT/'export';export.mkdir();keys=['conv.0.weight','conv.0.bias','conv.2.weight','conv.2.bias','conv.4.weight','conv.4.bias','fc1.weight','fc1.bias','fc2.weight','fc2.bias']
 weights=np.concatenate([saved['state_dict'][k].numpy().reshape(-1) for k in keys]).astype('<f4');assert len(weights)==17549 and np.isfinite(weights).all()
 weights.tofile(export/'weights.f32');shutil.copy2(ck,export/'model.pt');write(export/'complete.json',dict(parameters=17549,checkpoint_sha256=sha(ck),weights_sha256=sha(export/'weights.f32'),selection_sha256=sha(ROOT/'selected.json'),input_context=1.5,detector_confidence_metadata_zero=True))
 out=ROOT/'c_proof';out.mkdir();src=out/'source';src.mkdir();here=Path(__file__).parent
 old=(here/'road_patch_verifier.c').read_text();prefix=old[:old.index('float road_patch_logit(')].replace('"road_patch_verifier.h"','"road_box_refiner.h"').replace('*2.5f','*3.f').replace('meta[0]=b[4]','meta[0]=0.f')
 tail=r'''int road_box_refiner(const float *w,const uint8_t *rgb,const float meta[6],float *work,float output[5]){
 float *a=work,*b,*c,*d,*f,sum;int i,j,k;
 if(!w||!rgb||!meta||!work||!output)return 1;
 b=a+3072;c=b+2048;d=c+1024;f=d+384;
 for(i=0;i<1024;i++)for(j=0;j<3;j++)a[j*1024+i]=(float)rgb[i*3+j]/255.f;
 conv(w,w+216,a,3,32,32,b,8,16,16);conv(w+224,w+1376,b,8,16,16,c,16,8,8);conv(w+1392,w+4848,c,16,8,8,d,24,4,4);
 for(i=0;i<32;i++){
  sum=w[17352+i];for(j=0;j<384;j++)sum+=w[4872+i*390+j]*d[j];for(j=0;j<6;j++)sum+=w[4872+i*390+384+j]*meta[j];f[i]=sum>0.f?sum:0.f;
 }
 for(k=0;k<5;k++){sum=w[17544+k];for(i=0;i<32;i++)sum+=w[17384+k*32+i]*f[i];output[k]=sum;}
 return 0;
}
'''
 (src/'road_box_refiner.c').write_text(prefix+tail,encoding='ascii')
 (src/'road_box_refiner.h').write_text('#include <stdint.h>\n#define ROAD_REFINER_WEIGHT_FLOATS 17549U\n#define ROAD_REFINER_WORK_FLOATS 6560U\nint road_patch_features(const uint8_t *,const float *,uint8_t *,float *);\nint road_box_refiner(const float *,const uint8_t *,const float *,float *,float *);\n',encoding='ascii')
 zsrc=BASE/'road_car_zoom_20261030_r1/c_proof/source'
 for name in ['road_vehicle_multiview.h','road_fp32.h','road_graph.h']:shutil.copy2(zsrc/name,src/name)
 s=(zsrc/'road_car_zoom_fuse.c').read_text();s=s.replace('int road_car_zoom_fuse(','int road_car_refined_zoom(').replace('float weight,RoadBox *out','float weight,const float *pred,float strength,float cap,float classgate,RoadBox *out').replace('int i,j,t,n=0','int i,j,k,t,n=0')
 marker='   if(reject)continue;\n   b.score*=weight;';assert s.count(marker)==1
 refinement=r'''   if(reject)continue;
   {const float *d=pred+(t*300+i)*5;float w=b.x2-b.x1,h=b.y2-b.y1,cx,cy,nw,nh;
    for(k=0;k<5;k++){if(!isfinite(d[k]))return -6;}
    if(classgate>0.f&&1.f/(1.f+expf(-d[0]))<classgate)continue;
    cx=(b.x1+b.x2)*.5f+fmaxf(-cap,fminf(cap,d[1]))*strength*w;
    cy=(b.y1+b.y2)*.5f+fmaxf(-cap,fminf(cap,d[2]))*strength*h;
    nw=w*expf(fmaxf(-cap,fminf(cap,d[3]))*strength);nh=h*expf(fmaxf(-cap,fminf(cap,d[4]))*strength);
    b.x1=fmaxf(0.f,fminf(400.f,cx-nw*.5f));b.x2=fmaxf(0.f,fminf(400.f,cx+nw*.5f));
    b.y1=fmaxf(0.f,fminf(240.f,cy-nh*.5f));b.y2=fmaxf(0.f,fminf(240.f,cy+nh*.5f));
    if(b.x2<=b.x1||b.y2<=b.y1)continue;
    ba=area(&b);
    for(j=0;j<nf;j++)if(full[j].cls==b.cls&&full[j].score>=.25f){float v=inter(&b,full+j),fa=area(full+j);if(v/(ba+fa-v+1e-9f)>=.3f||v/(lo(ba,fa)+1e-9f)>=.8f){reject=1;break;}}
    if(reject)continue;
   }
   b.score*=weight;'''
 s=s.replace(marker,refinement);(src/'road_car_refined_zoom.c').write_text(s,encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_box_refiner.c'),str(src/'road_car_refined_zoom.c'),'-lm','-o',str(out/'refiner.dll')]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 engine=RefinerC();prepared=read(REF/'prepared.json');pixels=np.memmap(REF/'patches.u8',mode='r',dtype=np.uint8,shape=tuple(prepared['shape']));meta=np.fromfile(REF/'metadata.f32','<f4').reshape(-1,6)
 ids=np.random.default_rng(2026103082).choice(len(pixels),1024,replace=False);a=np.ascontiguousarray(pixels[ids]);m=meta[ids]
 with torch.inference_mode():expected=model(torch.from_numpy(a.transpose(0,3,1,2).copy()).cuda().float()/255,torch.from_numpy(m).cuda()).cpu().numpy()
 actual=np.stack([engine.predict(x,mm) for x,mm in zip(a,m)]);delta=np.abs(actual-expected);assert delta.max()<=.001 and delta.mean()<=.00002,(delta.max(),delta.mean())
 proof=dict(train_probe_cases=1024,network_max_abs=float(delta.max()),network_mean_abs=float(delta.mean()),cohorts={},source_immutable=True,buffer_canaries=True)
 for key,d in cohorts().items():
  local=locals_for(key);rows=[];maxcoord=0.;count=0
  for r in d['manifest']:
   name=r['name'];sensor,_=ac_sensor(d['images']/name);engine.begin(sensor);base=np.asarray(d['base'][name]['detections'],np.float32).reshape(-1,6);strong=base[base[:,4]>=.25]
   outputs=[np.zeros((len(v),5),np.float32) for v in d['views'][name]]
   for j,pp in enumerate(d['views'][name]):
    for i,b in enumerate(pp):
     b=np.asarray(b,np.float32)
     if not eligible(b,strong):continue
     image,m=engine.crop(b);ref_image,ref_meta=patch(sensor,b);assert image.tobytes()==ref_image.tobytes() and np.max(np.abs(m-ref_meta))<=1e-7
     outputs[j][i]=engine.predict(image,m);count+=1
   engine.end();actual=engine.fuse(base,local[name],outputs,chosen);expected=fuse_refined(base,d['views'][name],outputs,chosen['strength'],chosen['cap'],chosen['class_gate'])
   assert actual.shape==expected.shape and np.max(np.abs(actual-expected),initial=0)<=.0001,(key,name,actual.shape,expected.shape)
   maxcoord=max(maxcoord,float(np.max(np.abs(actual-expected),initial=0)));rows.append(dict(name=name,ground_truth=d['base'][name]['ground_truth'],detections=actual.tolist()))
  metrics=evaluate(rows)['classes']['car'];gg=gates(selected['baselines'][key],metrics);assert all(gg.values()),(key,gg)
  write(out/f'{key}_predictions.json',rows);proof['cohorts'][key]=dict(images=len(rows),eligible_refiner_calls=count,metrics=metrics,balanced_gates=gg,max_post_abs=maxcoord)
  print('BALANCED_C_REFINER_COHORT_PROVED',key,count,metrics,flush=True)
 proof.update(status='LEARNED_REFINER_AND_POST_PORTABLE_C_PROVED',dll_sha256=sha(out/'refiner.dll'),source_sha256={p.name:sha(p) for p in src.iterdir()},compiler=cmd,selection_sha256=sha(ROOT/'selected.json'),hardware_access=False,sd_written=False)
 write(ROOT/'c_complete.json',proof);shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('BALANCED_REFINER_C_PROOF_COMPLETE',proof['network_max_abs'],flush=True)

def ac_sensor(path):
 from road_accuracy_common import sensor400
 return sensor400(path)

if __name__=='__main__':main()
