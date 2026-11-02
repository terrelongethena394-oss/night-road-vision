"""Fixed-geometry confidence verification with raw-view sham control."""
from pathlib import Path
import ctypes as ct,os,shutil,subprocess,sys,time
import numpy as np
from road_enhanceadapt_common import BASE,INITIAL,AUDIT,read,write,sha
from road_numpy_eval import evaluate
ROOT=BASE/'road_car_consensus_20261030_r1'
GRID=[(p,b,s) for p in [0.,.3,.6] for b in [0.,.25,.5] for s in [0.,8.]]

class Consensus:
 def __init__(self,dll):
  self.lib=ct.CDLL(str(dll));self.fn=self.lib.road_car_consensus;self.fp=ct.POINTER(ct.c_float)
  self.fn.argtypes=[self.fp,ct.c_int,self.fp,ct.c_int,ct.c_float,ct.c_float,ct.c_float,self.fp,ct.c_int];self.fn.restype=ct.c_int
 def run(self,raw,helper,params):
  a=np.asarray(raw,np.float32).reshape(-1,6);b=np.asarray(helper,np.float32).reshape(-1,6)
  a=np.ascontiguousarray(a);b=np.ascontiguousarray(b);aa=a.tobytes();bb=b.tobytes()
  out=np.full((302,6),np.float32(12345.25));ptr=ct.cast(ct.c_void_p(out.ctypes.data+24),self.fp)
  n=self.fn(a.ctypes.data_as(self.fp),len(a),b.ctypes.data_as(self.fp),len(b),*params,ptr,300)
  assert 0<=n<=300 and np.all(out[[0,301]]==np.float32(12345.25)) and a.tobytes()==aa and b.tobytes()==bb
  return out[1:1+n].copy()

def numpy_reference(raw,helper,params):
 a=np.asarray(raw,np.float32).reshape(-1,6).copy();b=np.asarray(helper,np.float32).reshape(-1,6)
 p,boost,bypass=map(np.float32,params)
 for i,z in enumerate(a):
  w,h=z[2:4]-z[:2]
  if bypass>0 and (w<bypass or h<bypass):continue
  iw=np.maximum(np.float32(0),np.minimum(z[2:4],b[:,2:4])-np.maximum(z[:2],b[:,:2]));inter=iw.prod(1)
  ba=np.maximum(np.float32(0),b[:,2:4]-b[:,:2]).prod(1);iou=inter/(np.maximum(np.float32(0),w)*np.maximum(np.float32(0),h)+ba-inter+np.float32(1e-9))
  support=np.max(b[(iou>=np.float32(.3))&(b[:,5]==1),4]*np.minimum(np.float32(1),iou[(iou>=np.float32(.3))&(b[:,5]==1)]/np.float32(.5)),initial=np.float32(0))
  a[i,4]=np.clip(z[4]*(np.float32(1)-p*(np.float32(1)-support))+boost*(np.float32(1)-z[4])*support,0,1)
 a=a[(a[:,5]==1)&(a[:,4]>=np.float32(.001))]
 return a[np.argsort(-a[:,4],kind='stable')]

def gate(a,b):
 return dict(ap=b['ap50']>=a['ap50']+.005,precision=b['precision']>=a['precision']+.005,
             recall=b['recall']>=a['recall']-.005,false_positives=b['fp']<=.95*a['fp'])

def main():
 resume='--resume-build' in sys.argv
 assert not ROOT.exists() or (resume and not (ROOT/'selected.json').exists() and not (ROOT/'consensus.dll').exists())
 ROOT.mkdir(exist_ok=resume);src=ROOT/'source';src.mkdir(exist_ok=resume)
 if resume:
  shutil.copy2(ROOT/'build.log',ROOT/'initial_build_failure.log')
  shutil.copy2(src/'road_car_consensus.c',ROOT/'initial_source.c.txt')
 assert not read(BASE/'road_enhanceadapt_20261030_r1/delivery_selection.json')['qualified']
 assert sha(INITIAL)==read(AUDIT/'protocol.json')['model_sha256']
 protocol=dict(status='FROZEN_BEFORE_CONSENSUS_GRID_OR_ANY_NEW_TEST',
  hypothesis='Use enhancement as a second photometric verification view, not replace raw detection. Scores only, all coordinates from accepted raw4view detector. Same frozen accepted weights.',
  failure_preserved='Six-epoch mixed enhancement adaptation failed development; never ship it as a success.',
  features='Best enhanced-global confidence matching IoU>=0.3, weighted min(1,IoU/0.5). Score=s*(1-penalty*(1-support))+boost*(1-s)*support. Optional raw-box width/height<8 bypass.',
  grid=GRID,development='Explicitly reused audit320 low+96 brighter. No new blind-accuracy claim from this grid.',
  main_gates='CarAP>=initial+.5pp, precision>=initial+.5pp, recall>=initial-.5pp, FP<=95%initial; enhanced consensus AP must exceed best qualified raw-global sham by.2pp. Pick highest AP passing candidate.',
  sham='Same grid with helper=raw global, independently select best qualified control. This prevents relabelling score calibration as enhancement benefit.',
  fallback='If no primary enhanced candidate passes, a qualified raw-global consensus may be selected as detector-only fallback; explicitly no enhancement-attribution claim.',
  route='Raw mean<=48 selected consensus, otherwise unchanged accepted raw4view outputs. Enhanced consensus adds one forward; raw-global sham reuses existing global predictions with no new forward.',
  fresh_policy='After one candidate frozen,unused160 low+64 brighter excluding all recorded groups/hashes. All point gates plus99%paired bootstrap carAP lower>0 vs initial. If enhanced primary,99.5%lower>0 also vs best raw-global sham with fixed params. No test-driven replacement.',
  initial_checkpoint_sha256=sha(INITIAL),audit_result_sha256=sha(AUDIT/'result.json'),
  hardware_access=False,sd_written=False)
 if resume:assert read(ROOT/'protocol.json')==read_protocol_normalized(protocol)
 else:write(ROOT/'protocol.json',protocol)
 for name in ['road_car_consensus.c',Path(__file__).name]:shutil.copy2(Path(__file__).with_name(name),src/name)
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
 dll=ROOT/'consensus.dll';cmd=[str(gcc),'-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_car_consensus.c'),'-lm','-o',str(dll)]
 proc=subprocess.run(cmd,capture_output=True,text=True,env=env);(ROOT/'build.log').write_text(proc.stdout+proc.stderr);assert proc.returncode==0,proc.stderr
 engine=Consensus(dll);manifest=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json');cohort={r['name']:r['cohort'] for r in manifest}
 samples=[r for r in read(AUDIT/'predictions.json') if cohort[r['name']]=='low'];assert len(samples)==320
 baseline=read(AUDIT/'result.json')['scores']['low']['raw_multiview'];assert evaluate([r['raw_multiview'] for r in samples])['classes']['car']==baseline
 records=[];all_predictions={};begin=time.monotonic();maxdiff=0.;checks=0
 for mode,key in [('raw_sham','raw_global'),('enhanced','enh_global')]:
  for at,params in enumerate(GRID):
   predictions=[]
   for sample in samples:
    raw=sample['raw_multiview']['detections'];helper=sample[key]['detections']
    actual=engine.run(raw,helper,params);ref=numpy_reference(raw,helper,params)
    assert actual.shape==ref.shape and np.max(np.abs(actual-ref),initial=0)<=1e-6
    maxdiff=max(maxdiff,float(np.max(np.abs(actual-ref),initial=0)));checks+=1
    predictions.append(dict(name=sample['name'],ground_truth=sample['raw_multiview']['ground_truth'],detections=actual.tolist()))
   metrics=evaluate(predictions)['classes']['car'];gates=gate(baseline,metrics);tag=mode+'_'+str(at)
   records.append(dict(tag=tag,mode=mode,params=params,metrics=metrics,gates=gates,qualified=all(gates.values())))
   all_predictions[tag]=predictions
   print('CONSENSUS_DEVELOPMENT',tag,'AP',round(metrics['ap50'],5),'FP',metrics['fp'],'TP',metrics['tp'],'PASS',all(gates.values()),'seconds',round(time.monotonic()-begin),flush=True)
 sham=[r for r in records if r['mode']=='raw_sham' and r['qualified']]
 best_sham=max(sham,key=lambda r:r['metrics']['ap50']) if sham else None
 sham_ap=best_sham['metrics']['ap50'] if best_sham else baseline['ap50']
 good=[r for r in records if r['mode']=='enhanced' and r['qualified'] and r['metrics']['ap50']>=sham_ap+.002]
 chosen=max(good,key=lambda r:r['metrics']['ap50']) if good else best_sham
 result=dict(status='ONE_CONSENSUS_CANDIDATE_REQUIRES_UNUSED_CONFIRMATION' if chosen else 'NO_CONSENSUS_CANDIDATE_KEEP_ABI27',
  qualified=chosen is not None,chosen=chosen,best_raw_sham=best_sham,enhancement_primary_qualified=bool(good),
  baseline=baseline,records=records,protocol_sha256=sha(ROOT/'protocol.json'),
  no_new_test_predictions=True,hardware_access=False,sd_written=False)
 write(ROOT/'selected.json',result)
 write(ROOT/'c_numpy_proof.json',dict(cases=checks,max_abs=maxdiff,dll_sha256=sha(dll),compiler=cmd,input_immutable=True,output_canaries=True,geometry_unchanged=True))
 if chosen:write(ROOT/'chosen_predictions.json',all_predictions[chosen['tag']])
 if best_sham:write(ROOT/'sham_predictions.json',all_predictions[best_sham['tag']])
 print('CONSENSUS_SELECTION',result['qualified'],None if chosen is None else chosen['tag'],flush=True)

def read_protocol_normalized(value):
 import json
 return json.loads(json.dumps(value))

if __name__=='__main__':main()
