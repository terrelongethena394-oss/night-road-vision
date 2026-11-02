"""One frozen enhancement-trained candidate selection on explicitly reused data."""
import gc,shutil,time
import numpy as np
from PIL import Image
import road_accuracy_common as ac
from road_numpy_eval import evaluate
from road_enhanceadapt_common import *

def metrics(rows,key):
 return evaluate([r[key] for r in rows])['classes']['car']

def assess(det,manifest,images,labels,enhanced_dir,out):
 out.mkdir(parents=True,exist_ok=True)
 if (out/'complete.json').exists():return read(out/'predictions.json')
 samples=[];begin=time.monotonic()
 for at in range(0,len(manifest),8):
  rr=manifest[at:at+8];ims=[]
  for r in rr:
   sensor,full=ac.sensor400(images/r['name']);enh=np.asarray(Image.open(enhanced_dir/r['name']))
   ims.extend([full,enh]+[sensor[y:y+240,x:x+400] for x,y in ac.TILES])
  pp=det.run(ims)
  for i,r in enumerate(rr):
   p=pp[5*i:5*i+5];tiles=[ac.map_tile(p[j+2],*ac.TILES[j]) for j in range(3)]
   gt=ac.truth(labels/(Path(r['name']).stem+'.txt'));car=gt[gt[:,0]==1]
   sample=dict(name=r['name'],ground_truth_all=gt.tolist(),
    views=dict(raw_global=p[0],enh_global=p[1],**{f'raw_tile{j}':p[j+2] for j in range(3)}))
   for key,pred in [('raw',ac.fuse(p[0],tiles,.75)),('enh',ac.fuse(p[1],tiles,.75))]:
    sample[key]=dict(name=r['name'],ground_truth=car.tolist(),detections=pred[pred[:,5]==1].tolist())
   samples.append(sample)
  if (at+len(rr))%80==0:print('ENHANCEADAPT_EVALUATE',out.name,at+len(rr),len(manifest),round(time.monotonic()-begin),flush=True)
 write(out/'predictions.json',samples)
 write(out/'complete.json',dict(images=len(manifest),source_model_sha256=getattr(det,'checkpoint_sha',None),seconds=time.monotonic()-begin,predictions_sha256=sha(out/'predictions.json'),hardware_access=False))
 return samples

def comparison(initial,raw,enh):
 return dict(ap_gain_vs_initial=enh['ap50']>=initial['ap50']+.005,
             ap_gain_vs_same_model_raw=enh['ap50']>=raw['ap50']+.005,
             precision=enh['precision']>=initial['precision']-.005,
             recall=enh['recall']>=initial['recall']-.005,
             false_positives=enh['fp']<=initial['fp'])

def main():
 assert (ROOT/'training_complete.json').exists() and not (ROOT/'selected.json').exists()
 import torch
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 manifest=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json')
 low=[r for r in manifest if r['cohort']=='low'];assert len(low)==320
 initial=read(AUDIT/'result.json')['scores']['low']['raw_multiview']
 prior={r['name']:r for r in read(AUDIT/'predictions.json')}
 assert sha(AUDIT/'protocol.json')==read(AUDIT/'result.json')['protocol_sha256']
 identity=read(AUDIT/'protocol.json');assert sha(INITIAL)==identity['model_sha256']
 assert sha(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json')==identity['manifest_sha256']
 ac.WEIGHTS=INITIAL;det=ac.Detector();records=[]
 data=BASE/'road_brightness_route_20261030_r1/fresh'
 for epoch in CHECKPOINTS:
  ck=ROOT/'frozen'/f'epoch{epoch}/model.pt';assert sha(ck)==read(ck.with_name('frozen.json'))['sha256']
  del det.model;gc.collect();torch.cuda.empty_cache()
  det.model=torch.load(ck,map_location='cpu',weights_only=False)['model'].float().fuse().eval().cuda();det.checkpoint_sha=sha(ck)
  samples=assess(det,low,data/'images',data/'labels',AUDIT/'enhanced',ROOT/'development'/f'epoch{epoch}')
  raw=metrics(samples,'raw');enh=metrics(samples,'enh');gates=comparison(initial,raw,enh)
  # Bright branch is the accepted initial model, not a tuned new checkpoint.
  routed=[]
  byname={r['name']:r for r in samples}
  for r in manifest:
   routed.append(byname[r['name']]['enh'] if r['cohort']=='low' else prior[r['name']]['raw_multiview'])
  bright=[p for p,r in zip(routed,manifest) if r['cohort']=='brighter']
  bright_prior=[prior[r['name']]['raw_multiview'] for r in manifest if r['cohort']=='brighter']
  assert bright==bright_prior
  gates['brighter_route_unchanged']=True
  write(ROOT/'development'/f'epoch{epoch}/routed_predictions.json',routed)
  record=dict(epoch=epoch,checkpoint=str(ck),sha256=sha(ck),initial_raw=initial,same_model_raw=raw,enhanced=enh,gates=gates,passes=all(gates.values()))
  records.append(record);write(ROOT/'development_progress.json',records)
  print('ENHANCEADAPT_EPOCH_RESULT',epoch,'passed',record['passes'],'raw_ap',raw['ap50'],'enh_ap',enh['ap50'],'enh_fp',enh['fp'],'gates',gates,flush=True)
 good=[r for r in records if r['passes']];chosen=max(good,key=lambda r:r['enhanced']['ap50']) if good else None
 selected=dict(status='DEVELOPMENT_PASS_REQUIRES_UNUSED_CONFIRMATION' if chosen else 'NO_CHECKPOINT_PASSED_KEEP_ABI27',
  qualified=bool(chosen),chosen=chosen,records=records,protocol_sha256=sha(ROOT/'protocol.json'),
  selection_data='Reused audit416, now development; not independent evidence.',fresh_inference=False,hardware_access=False,sd_written=False)
 write(ROOT/'selected.json',selected)
 print('ENHANCEADAPT_SELECTION',None if chosen is None else chosen['epoch'],flush=True)

if __name__=='__main__':main()
