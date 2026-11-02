"""Diagnostic real-photo examples: same raw pixels, all320 metrics reported separately."""
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from road_brightness_route_common import *
from road_accuracy_common import sensor400,correct

def score(row):
 p=np.asarray(row['detections'],np.float32).reshape(-1,6);p=p[(p[:,5]==1)&(p[:,4]>=.25)];g=np.asarray(row['ground_truth'],np.float32).reshape(-1,5);ok=correct(p,g,np.array([.5],np.float32))[0][:,0];return p,int(ok.sum()),int(len(ok)-ok.sum())

def main():
 assert (ROOT/'fresh_result.json').exists();old=read(ROOT/'fresh_evaluation/baseline/native/candidate_predictions.json');new=read(ROOT/'fresh_evaluation/routed_predictions.json');manifest=read(ROOT/'fresh/manifest.json');candidates=[]
 for a,b,m in zip(old,new,manifest):
  if m['cohort']!='low':continue
  pa,ta,fa=score(a);pb,tb,fb=score(b);candidates.append(dict(name=a['name'],old=a,new=b,tp0=ta,tp1=tb,fp0=fa,fp1=fb))
 selected=[];used=set()
 rules=[('GAIN',lambda r:r['tp1']>r['tp0'] and r['fp1']<=r['fp0'],2),('REGRESSION',lambda r:r['tp1']<r['tp0'] or r['fp1']>r['fp0'],1)]
 for tag,fn,count in rules:
  pool=sorted([r for r in candidates if fn(r)],key=lambda r:r['name'])
  for r in pool:
   if r['name'] in used:continue
   selected.append((tag,r));used.add(r['name'])
   if sum(t==tag for t,_ in selected)==count:break
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);canvas=Image.new('RGB',(800,280*len(selected)+40),(20,20,20));receipts=[]
 for at,(tag,r) in enumerate(selected):
  _,raw=sensor400(ROOT/'fresh/images'/r['name'])
  for column,key,color in [(0,'old',(30,220,255)),(1,'new',(80,255,100))]:
   im=Image.fromarray(raw);d=ImageDraw.Draw(im);p,tp,fp=score(r[key])
   for box in p:d.rectangle(tuple(box[:4]),outline=color,width=1)
   x=column*400;y=at*280;canvas.paste(im,(x,y+40));d=ImageDraw.Draw(canvas);d.text((x+4,y+2),('STABLE' if column==0 else 'CANDIDATE')+f' / CAR ONLY / TP {tp} FP {fp}',fill='white',font=font);d.text((x+4,y+21),tag+' '+r['name'],fill='white',font=font)
  receipts.append({k:r[k] for k in ['name','tp0','tp1','fp0','fp1']}|dict(tag=tag,source=str(ROOT/'fresh/images'/r['name'])))
 d=ImageDraw.Draw(canvas);d.text((5,len(selected)*280+7),'Selected examples, including regression. Quantitative results use ALL320 low-light photos.',fill='white',font=font)
 canvas.save(ROOT/'car_examples_with_regression.png');write(ROOT/'car_examples_with_regression.json',receipts);print('ROUTED_CAR_EXAMPLES_SAVED',len(selected),flush=True)

if __name__=='__main__':main()
