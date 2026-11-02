"""Diagnostic contact sheet from real cached images and original annotations."""
from PIL import Image,ImageDraw,ImageFont
from audit_multiview_errors import ROOT,COHORTS,overlap
from road_accuracy_common import BASE,DATA,read,write,sensor400,NAMES
import numpy as np

def main():
 records=read(ROOT/'box_audit.json');chosen=[];used=set()
 for cohort in ['original320','low320']:
  for r in records:
   if r['cohort']!=cohort or r['original'] or r['tp'] or r['other_gt_iou']<.7 or r['same_gt_iou']>=.1 or r['name'] in used:continue
   chosen.append(r);used.add(r['name'])
   if sum(z['cohort']==cohort for z in chosen)==2:break
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);canvas=Image.new('RGB',(600,280*len(chosen)),(20,20,20));receipts=[]
 for at,r in enumerate(chosen):
  folder=COHORTS[r['cohort']];rows=read(folder/'global_raw.json');row=next(z for z in rows if z['name']==r['name'])
  path=DATA/'dataset/images/val'/r['name'] if r['cohort']=='original320' else BASE/'road_accuracy_lowlight_20261030_r1/fresh/images'/r['name']
  _,rgb=sensor400(path);im=Image.fromarray(rgb);draw=ImageDraw.Draw(im);gt=np.asarray(row['ground_truth'],np.float32).reshape(-1,5);other=gt[gt[:,0]!=NAMES.index(r['cls'])];j=int(np.argmax(overlap(np.asarray(r['box'],np.float32),other[:,1:])))
  truth=other[j];draw.rectangle(tuple(truth[1:]),outline=(50,255,50),width=2);draw.rectangle(tuple(r['box'][:4]),outline=(255,60,60),width=1)
  cropbox=tuple([max(0,int(r['box'][0])-25),max(0,int(r['box'][1])-20),min(400,int(r['box'][2])+25),min(240,int(r['box'][3])+20)]);crop=im.crop(cropbox);crop.thumbnail((196,236));canvas.paste(im,(0,at*280+40));canvas.paste(crop,(402,at*280+40))
  d=ImageDraw.Draw(canvas);d.text((5,at*280+3),r['name']+' / '+r['cohort'],font=font,fill='white');d.text((5,at*280+21),'RED extra '+r['cls']+' FP; GREEN annotation '+NAMES[int(truth[0])],font=font,fill='white');receipts.append(dict(record=r,annotation=truth.tolist(),source=str(path)))
 canvas.save(ROOT/'error_examples.png');write(ROOT/'error_examples.json',receipts);print(ROOT/'error_examples.png')

if __name__=='__main__':main()
