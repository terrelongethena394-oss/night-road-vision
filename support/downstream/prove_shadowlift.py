"""C/NumPy implementation proof and display guardrails on known scenes/controls."""
from pathlib import Path
import ctypes as ct,os,shutil,subprocess,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from shadowlift_lab import BASE,ROOT,OLD,read,write,sha,words,unpack,Baseline,mean_y
from shadowlift_refine import final_display
from road_accuracy_common import sensor400

def main():
 resume='--resume-failed' in sys.argv;out=ROOT/'c_proof';assert not out.exists() or (resume and not (ROOT/'c_complete.json').exists());out.mkdir(exist_ok=resume);here=Path(__file__).resolve().parent;src=out/'source';src.mkdir(exist_ok=resume)
 if (out/'build.log').exists() and not (out/'initial_build_failure.log').exists():shutil.copy2(out/'build.log',out/'initial_build_failure.log')
 write(ROOT/'selected.json',dict(status='SELECTED_BY_INSPECTING_KNOWN_SCENE_PREVIEWS_BEFORE_C_PROOF',target_luma=62,strength_limit=5,raw_gain_limit=10,chroma_mix=.85,chroma_window=5,normal_brightness='No extra processing if frozen baseline mean>=62',rationale='70/88 visibly amplified noise and glare;62 improves shadow visibility more conservatively. Chroma-only cleanup and gamut projection preserve luminance detail and prevent newly saturated pixels. No new spatial luminance blur.',models_and_weights_unchanged=True,no_blind_quality_claim=True,sd_written=False))
 for n in ['road_shadowlift.c','road_shadowlift.h','road_retinex_shadow.c']:shutil.copy2(here/n,src/n)
 shutil.copy2(OLD/'firmware/source/road_retinex_c.h',src/'road_retinex_c.h');s=(OLD/'firmware/source/road_retinex_c.c').read_text();assert s.count('int road_retinex_c(')==1;s=s.replace('for(c=0;c<3;c++)value|=(uint32_t)floorf(clip(rgb[c],0.f,255.f)+.5f)<<(8*c);dst[at]=value;','for(c=0;c<3;c++){value|=(uint32_t)floorf(clip(rgb[c],0.f,255.f)+.5f)<<(8*c);}\n  dst[at]=value;');(src/'road_retinex_base.c').write_text(s.replace('int road_retinex_c(','int road_retinex_base('),encoding='ascii')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];dll=out/'shadow.dll';cmd=[str(gcc),'-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_retinex_base.c'),str(src/'road_shadowlift.c'),str(src/'road_retinex_shadow.c'),'-lm','-o',str(dll)];p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
 class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
 lib=ct.CDLL(str(dll));up=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);lib.road_retinex_c.argtypes=[up,up,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
 baseline=Baseline();cases=[]
 for name in ['current_road','dark_traffic','city_control']:cases.append((name,unpack(np.fromfile(ROOT/name/'raw.u32','<u4')).reshape(240,400,3)))
 for value in [0,1,4,16,48,96,245,255]:cases.append(('gray'+str(value),np.full((240,400,3),value,np.uint8)))
 ramp=np.repeat(np.arange(400,dtype=np.float32)[None,:,None]*255/399,240,0);ramp=np.repeat(ramp,3,2).astype(np.uint8);cases.append(('ramp',ramp));rgb=np.zeros((240,400,3),np.uint8)
 for k in range(3):rgb[:,k*133:(k+1)*133,k]=24
 cases.append(('dark_RGB',rgb))
 dataset=BASE/'road_brightness_route_20261030_r1/fresh';manifest=read(dataset/'manifest.json')
 for group in ['low','brighter']:
  for r in sorted([r for r in manifest if r['cohort']==group],key=lambda r:r['name'])[:12]:cases.append((Path(r['name']).stem,sensor400(dataset/'images'/r['name'])[1]))
 records=[];work_size=17*96000+65536
 for name,raw in cases:
  base=baseline.run(raw);expected,stats=final_display(raw,base);a=words(raw).reshape(-1);aa=a.tobytes();b=np.full(96002,0x12345678,np.uint32);w=np.empty(work_size+2,np.float32);w.view(np.uint32)[[0,-1]]=0x3f987654;ws=ct.cast(ct.c_void_p(w.ctypes.data+4),fp);bp=ct.cast(ct.c_void_p(b.ctypes.data+4),up);rs=Stats();assert lib.road_retinex_c(a.ctypes.data_as(up),bp,96000,ws,ct.byref(rs),None,None)==0
  actual=unpack(b[1:-1]).reshape(240,400,3);d=np.abs(actual.astype(np.int16)-expected.astype(np.int16));assert d.max()<=1 and d.mean()<=.01,(name,d.max(),d.mean());assert b[0]==b[-1]==0x12345678 and np.all(w.view(np.uint32)[[0,-1]]==0x3f987654) and a.tobytes()==aa
  assert not np.any((actual.max(2)==255)&(base.max(2)<255)),name
  if stats['strength']==0:assert actual.tobytes()==base.tobytes(),name
  if name in ['gray0','gray255']:assert actual.tobytes()==base.tobytes()
  records.append(dict(name=name,max_abs=int(d.max()),mean_abs=float(d.mean()),mean_raw=mean_y(raw),mean_baseline=mean_y(base),mean_new=mean_y(actual),strength=stats['strength'],new_saturated_pixels=0))
  if name in ['current_road','dark_traffic','city_control']:
   Image.fromarray(actual).save(ROOT/name/'FINAL_C.png');words(actual).tofile(ROOT/name/'final.u32')
 # Invalid size and alias must return without modifying the source.
 a=words(cases[0][1]).reshape(-1);before=a.tobytes();w=np.empty(work_size,np.float32);stats=Stats();assert lib.road_retinex_c(a.ctypes.data_as(up),a.ctypes.data_as(up),96000,w.ctypes.data_as(fp),ct.byref(stats),None,None)!=0 and a.tobytes()==before
 write(ROOT/'c_complete.json',dict(status='DISPLAY_SHADOWLIFT_C_NUMPY_AND_GUARDRAILS_PASS',cases=len(records),records=records,source_sha256={p.name:sha(p) for p in src.iterdir()},dll_sha256=sha(dll),compiler=cmd,input_immutable=True,work_and_output_canaries=True,no_new_saturation=True,normal_brightness_byte_exact=True,max_abs_tolerance=1,mean_abs_tolerance=.01,hardware_access=False,sd_written=False));print('SHADOWLIFT_C_PROVED',len(records),'max',max(r['max_abs'] for r in records),'meanmax',max(r['mean_abs'] for r in records),flush=True)
 canvas=Image.new('RGB',(1200,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
 for row,name in enumerate(['current_road','dark_traffic','city_control']):
  for col,(tag,file) in enumerate([('RAW','RAW.png'),('PREVIOUS','CURRENT.png'),('NEW DISPLAY','FINAL_C.png')]):
   im=Image.open(ROOT/name/file);canvas.paste(im,(col*400,row*280+40));d=ImageDraw.Draw(canvas);d.text((col*400+5,row*280+4),name+' '+tag,fill='white',font=font)
 canvas.save(ROOT/'final_comparison.png')

if __name__=='__main__':main()
