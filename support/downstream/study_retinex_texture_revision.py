"""Frozen manual-feedback revision on known illustrations; not a blind test."""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image
from road_retinex_detail import enhance,PRESETS
from study_road_local_enhance import panel,metric
ROOT=Path('E:/FPGA_Enhance_Work/road_retinex_detail_20261029_r1')
BASE=Path('E:/FPGA_Enhance_Work')
REF=BASE/'road_project_retinex_20261029_r3'
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def rgbwords(p):
 v=np.fromfile(p,'<u4').reshape(240,400);return np.stack([v&255,v>>8&255,v>>16&255],2).astype(np.uint8)
def main():
 assert not ROOT.exists();ROOT.mkdir()
 source=Path(__file__).resolve().parent/'road_retinex_detail.py'
 protocol=dict(status='FROZEN_BEFORE_DETAIL_REVISION_OUTPUTS',reason='Manual rejection: sky and hood smeared, vehicles clearer. Same-gain ablation confirms strong spatial luminance/RGB smoothing. Keep original luminance outside filtering; cap gain and use patch similarity only for chroma.',parameters=PRESETS,default='detail_balanced',default_selection='Fixed before outputs based on manual complaint, no selection from paired20 outcomes',showcase_names=['c81ff2c0-420a8956','b8acc534-d5b64200','baa88157-4026332f'],pretrained_weights=False,hardware_access=False,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
 write(ROOT/'protocol.json',protocol);shutil.copy2(source,ROOT/source.name)
 records=[]
 for name in protocol['showcase_names']:
  raw=np.array(Image.open(REF/'showcase'/name/'raw.png').convert('RGB'))
  old=rgbwords(BASE/'road_retinex_balanced_20261029_r1/firmware/runtime/cases'/name/'enhanced400.u32')
  folder=ROOT/name;folder.mkdir();outs={}
  for m in PRESETS:
   z,s=enhance(raw,m);assert s['luminance_reconstruction_max_float_error']<.0001
   Image.fromarray(z).save(folder/(m+'.png'));outs[m]=z;records.append(dict(name=name,method=m,**s))
  Image.fromarray(raw).save(folder/'raw.png')
  panel([raw,old,outs['detail_balanced']],['原图','当前50%：仍有涂抹','新候选：保留亮度纹理'],name,folder/'comparison.png',note='同一照片；电脑候选，尚未上板；不使用车辆框指导增强。')
  print('DETAIL_REVISION_CASE',name,[r for r in records if r['name']==name],flush=True)
 # Already-used paired20 remains descriptive regression, not parameter tuning.
 scores=[]
 for folder in sorted((REF/'paired_regression').iterdir()):
  if not folder.is_dir():continue
  raw=np.array(Image.open(folder/'raw.png').convert('RGB'));gt=np.array(Image.open(folder/'normal_reference.png').convert('RGB'))
  z,_=enhance(raw,'detail_balanced');scores.append(dict(name=folder.name,**metric(z,gt)))
 write(ROOT/'paired20_regression.json',dict(images=len(scores),method='detail_balanced',psnr=float(np.mean([r['psnr'] for r in scores])),ssim=float(np.mean([r['ssim'] for r in scores])),rows=scores,not_new_blind_test=True))
 write(ROOT/'complete.json',dict(status='TEXTURE_PRESERVING_OFFLINE_REVISION_READY_NOT_BOARD_TESTED',records=records,sd_written=False))
if __name__=='__main__':main()
