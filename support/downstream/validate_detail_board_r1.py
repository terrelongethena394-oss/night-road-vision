from pathlib import Path
import struct,json,subprocess,statistics,sys
import numpy as np
from road_enhance_common import enhance
from road_arm_common import preprocess400
from verify_road_arm_host import compare_boxes
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_detail_board_20261028_r1';APP=ROOT/'firmware';BOARD=APP/'physical_r1';REF=BASE/'road_roi_spatial_verifier_20261028'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def rgb(b):
 a=np.frombuffer(b,'<u4').reshape(240,400);return np.stack([a&255,(a>>8)&255,(a>>16)&255],2).astype(np.uint8)
def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h
def words(p):
 b=p.read_bytes();assert len(b)==512;return struct.unpack('<128I',b)
def mail(m,detail,pl,live=False):
 assert m[:4]==(0x524f4144,15,3,1) and m[6]==0 and m[57]==1
 assert m[30]==0x7084 and m[40]==0x5640 and m[35]==m[41]==m[74]==0
 assert m[72]==pl
 if not live:assert m[73]==12*pl and m[103]==12*pl and m[104]==12*pl*(1+detail)
 assert m[99]==detail and m[80]==m[93]==2 and m[81]==32 and m[17]==1483844061 and m[77]==0x5041434b
def floats(a,b,decoded=False):
 assert a.shape==b.shape and np.isfinite(a).all();d=abs(a-b)
 if decoded:assert d[:,:4].max()<=.02 and d[:,4:].max()<=2e-4,float(d.max())
 else:assert np.all(d<=1e-4+1e-4*abs(b)),float(d.max())
 return float(d.max(initial=0))
def native(name,kind):return REF/kind/'cases'/name/'host'
def heads(folder):return np.concatenate([np.fromfile(folder/'trace'/f'{tid:03d}.f32','<f4') for tid in [83,84,85]])
def frame(p):
 m=words(p/'mail.bin');u=struct.unpack('<16I',(p/'ui.u32').read_bytes());raw=(p/'raw.u32').read_bytes();en=(p/'enhanced.u32').read_bytes();expected,s=enhance(rgb(raw),1,32);assert np.array_equal(expected,rgb(en));assert m[91]==fnv(raw) and m[92]==fnv(en);assert u[11]==s['mean_in'] and u[12]==s['alpha'] and u[14]==2 and u[15]==m[99]
 z=subprocess.run([str(APP/'host/render.exe'),str(p/'left.u32'),str(p/'enhanced.u32'),str(p/'boxes.f32'),str(p/'ui.u32'),str(p/'expected.bgr')],capture_output=True,text=True);assert z.returncode==0 and 'GUARDS_PASS' in z.stdout;assert (p/'expected.bgr').read_bytes()==(p/'frame.bgr').read_bytes();assert m[37]==fnv((p/'frame.bgr').read_bytes())
 source=np.fromfile(p/'capture.bgr',np.uint8).reshape(480,800,3);a=((source.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32);assert (a[:,:,2]|(a[:,:,1]<<8)|(a[:,:,0]<<16)).astype('<u4').tobytes()==(p/'live.u32').read_bytes()
 if m[94]:
  a=source[120:360,200:600].astype(np.uint32);assert (a[:,:,2]|(a[:,:,1]<<8)|(a[:,:,0]<<16)).astype('<u4').tobytes()==(p/'live_roi.u32').read_bytes();assert m[119]==fnv((p/'roi.u32').read_bytes())
 return dict(detail=m[99],result_id=u[1],latest_preview_id=u[0],pixels_exact=True,enhancement=s)
def main():
 if '--early' not in sys.argv:assert (BOARD/'COMPLETE').exists()
 cases=read(APP/'arm_complete.json')['cases'];first=cases[0]['name'];results=[]
 def packet(p,name,detail,pl=1):
  m=words(p/'mail.bin');mail(m,detail,pl);assert m[62]==0
  fixture=APP/'runtime/cases'/name;assert (p/'raw.u32').read_bytes()==(fixture/'input400.u32').read_bytes();assert m[16]==fnv((p/'raw.u32').read_bytes())
  full=native(name,'native_detector_full');roi=native(name,'native_detector_roi');ref=roi if detail else full
  h=floats(np.fromfile(p/'heads.f32','<f4'),heads(ref));floats(np.fromfile(p/'decoded.f32','<f4').reshape(-1,9),np.fromfile(ref/'decoded.f32','<f4').reshape(-1,9),True)
  prep=p/('full_prep.rgb' if detail else 'prep.rgb');assert prep.read_bytes()==(full/'input320.rgb').read_bytes()
  if detail:
   assert (p/'roi.u32').read_bytes()==(fixture/'roi400.u32').read_bytes();assert (p/'prep.rgb').read_bytes()==(roi/'input320.rgb').read_bytes();floats(np.fromfile(p/'full_heads.f32','<f4'),heads(full));floats(np.fromfile(p/'full_decoded.f32','<f4').reshape(-1,9),np.fromfile(full/'decoded.f32','<f4').reshape(-1,9),True)
  boxes=compare_boxes(np.fromfile(p/'boxes.f32','<f4').reshape(-1,6),np.fromfile(fixture/('gold_detail_boxes400.f32' if detail else 'gold_raw_boxes400.f32'),'<f4').reshape(-1,6),.04)
  return dict(name=name,detail=detail,pl=pl,head_max_abs=h,boxes=boxes,frame=frame(p))
 if '--early' in sys.argv:
  rows=[packet(BOARD/f'{first}_mode0',first,0),packet(BOARD/f'{first}_mode1',first,1),packet(BOARD/'cpu_detail',first,1,0)]
  for n in ['heads.f32','decoded.f32','full_heads.f32','full_decoded.f32','boxes.f32']:assert (BOARD/'cpu_detail'/n).read_bytes()==(BOARD/f'{first}_mode1'/n).read_bytes(),n
  (ROOT/'early_validated.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print('FIRST_RAW_DETAIL_AND_CPU_FPGA_AND_FRAMES_PASS',flush=True);return
 for r in cases:
  for mode in [0,1]:results.append(packet(BOARD/f"{r['name']}_mode{mode}",r['name'],mode))
 results.append(packet(BOARD/'cpu_detail',first,1,0));results.append(packet(BOARD/'trace_first',first,1))
 for n in ['heads.f32','decoded.f32','full_heads.f32','full_decoded.f32','boxes.f32']:assert (BOARD/'cpu_detail'/n).read_bytes()==(BOARD/f'{first}_mode1'/n).read_bytes(),n
 data=(BOARD/'trace_first/all86.f32').read_bytes();off=0;layers=[]
 for t in read(BASE/'road_arm_prototype_20261026/graph.json')['tensors']:
  size=t['elements']*4;a=np.frombuffer(data[off:off+size],'<f4');b=np.fromfile(native(first,'native_detector_full')/'trace'/f"{t['id']:03d}.f32",'<f4');layers.append(floats(a,b));off+=size
 assert off==len(data)==19844800
 live=[]
 for mode in [0,1]:
  p=BOARD/f'live{mode}';mail(words(p/'mail.bin'),mode,1,live=True);f=frame(p);start,finish,begin,done,vbegin,views=map(int,(p/'cadence.txt').read_text().split());live.append(dict(mode=mode,seconds=(finish-start)/1000,completed=done-begin,preview_updates=views-vbegin,detection_hz=1000*(done-begin)/(finish-start),preview_hz=1000*(views-vbegin)/(finish-start),frame=f))
 timing={}
 for mode in [0,1]:
  rows=[]
  for i in range(4):
   m=words(BOARD/f'timing{mode}_{i}.bin');mail(m,mode,1);rows.append((m[19]+(m[20]<<32))/m[18])
  timing[str(mode)]=dict(warmup=rows[0],runs=rows[1:],median_seconds=statistics.median(rows[1:]))
 result=dict(status='ROI_EXPERIMENT_FIXED14_CPU_FPGA_ALL86_LIVE_BOTH_MODES_VALIDATED',fixed=results,first_cpu_fpga_all_outputs_byte_exact=True,trace86_max=max(layers),timing=timing,live=live,sd_written=False);(ROOT/'validated.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DETAIL_BOARD_VALIDATED',timing,live,flush=True)
if __name__=='__main__':main()
