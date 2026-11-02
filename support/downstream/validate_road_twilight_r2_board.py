"""Strict new-model board/C agreement, including CPU/PL byte equality and live RGB."""
from pathlib import Path
import struct,statistics,subprocess
import numpy as np
from road_twilight_r2_common import ROOT,NN,read,write
from road_enhance_common import enhance
from road_arm_common import preprocess400
from verify_road_arm_host import compare_boxes
APP=ROOT/'firmware';BOARD=APP/'board_fixed_r1'
def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h
def words(p):
 b=Path(p).read_bytes();assert len(b)==384;return struct.unpack('<96I',b)
def rgb(b):
 a=np.frombuffer(b,'<u4').reshape(240,400);return np.stack([a&255,(a>>8)&255,(a>>16)&255],2).astype(np.uint8)
def mail(m,pl,pipe,model_fnv):
 assert m[0]==0x524f4144 and m[1]==14 and m[2]==3 and m[3]==1 and m[6]==0 and m[57]==1
 assert m[30]==0x7084 and m[40]==0x5640 and m[35]==m[41]==0 and m[72]==pl and m[74]==0 and m[77]==0x5041434b
 assert m[80]==pipe and m[93]==pipe and m[81]==32 and m[17]==model_fnv
 if pl==0:assert m[73]==0
def floats(a,b,label,decoded=False):
 assert a.shape==b.shape and np.isfinite(a).all();d=abs(a-b)
 if decoded:assert d[:,:4].max()<=.02 and d[:,4:].max()<=2e-4,(label,float(d.max()))
 else:assert np.all(d<=1e-4+1e-4*abs(b)),(label,float(d.max()))
 return float(d.max(initial=0))
def pair(raw,enh,pipe):
 a=rgb(raw);b=rgb(enh);e,s=enhance(a,1,32);assert np.array_equal(e,b);return e if pipe==1 else a,s
def main():
 assert (BOARD/'COMPLETE.txt').read_text().strip()=='ROAD_TWILIGHT_FULL_TEST_READBACK_COMPLETE';proof=read(APP/'arm_complete.json');pipe=proof['default_pipe'];mf=proof['weight_fnv32'];cases=proof['cases'];first=cases[0]['name'];kind='native_enh' if pipe==1 else 'native_raw'
 def packet(p,name,pl,full=False):
  m=words(p/('mailbox.bin' if full else 'mailbox96.bin'));mail(m,pl,pipe,mf);assert m[73]==(12 if pl else 0) and m[62]==0
  raw=(p/'raw_result400.u32').read_bytes();enh=(p/('result400.u32' if full else 'enhanced400.u32')).read_bytes();effective,stats=pair(raw,enh,pipe)
  assert raw==(ROOT/'native_raw/cases'/name/'input400.u32').read_bytes() and m[16]==fnv(raw);assert m[82:87]==tuple(stats[k] for k in ['mean_in','mean_out','alpha','changed','max_delta'])
  assert (p/'preprocessed.rgb').read_bytes()==preprocess400(effective).tobytes();ref=ROOT/kind/'cases'/name/'host';maxerr=0.
  for j,tid in enumerate([83,84,85]):maxerr=max(maxerr,floats(np.fromfile(p/f'head{j}.f32','<f4'),np.fromfile(ref/'trace'/f'{tid:03d}.f32','<f4'),(name,j)))
  floats(np.fromfile(p/'decoded.f32','<f4').reshape(-1,9),np.fromfile(ref/'decoded.f32','<f4').reshape(-1,9),name,True)
  bx=compare_boxes(np.fromfile(p/'boxes400.f32','<f4').reshape(-1,6),np.fromfile(ref/'boxes400.f32','<f4').reshape(-1,6),.04)
  return dict(name=name,pl_mode=pl,pipe_mode=pipe,stats=stats,head_max_abs=maxerr,boxes=bx)
 packets=[packet(BOARD/'cpu_first',first,0)]+[packet(BOARD/r['name'],r['name'],1) for r in cases]
 for n in ['decoded.f32','boxes400.f32','head0.f32','head1.f32','head2.f32']:assert (BOARD/'cpu_first'/n).read_bytes()==(BOARD/first/n).read_bytes(),('CPU PL difference',n)
 full=BOARD/'first_default_full';packet(full,first,1,True);trace=(full/'all_layers.f32').read_bytes();off=0;layers=[]
 for t in read(NN/'graph.json')['tensors']:
  n=t['elements']*4;a=np.frombuffer(trace[off:off+n],'<f4');b=np.fromfile(ROOT/kind/'cases'/first/'host/trace'/f'{t["id"]:03d}.f32','<f4');off+=n;layers.append(dict(id=t['id'],max_abs=floats(a,b,t['id'])))
 assert off==len(trace)==19844800
 frames=[]
 for p in [full,BOARD/'live_default']:
  m=words(p/'mailbox.bin');mail(m,1,pipe,mf);u=struct.unpack('<15I',(p/'ui.u32').read_bytes());assert u[14]==pipe
  raw=(p/'raw_result400.u32').read_bytes();enh=(p/'result400.u32').read_bytes();live=(p/'live400.u32').read_bytes();frame=(p/'frame.bgr').read_bytes();e,s=pair(raw,enh,pipe)
  assert u[11]==s['mean_in'] and u[12]==s['alpha'];assert m[91]==fnv(raw) and m[92]==m[64]==fnv(enh) and m[65]==fnv(live) and m[37]==fnv(frame)
  source=np.fromfile(p/'capture_source.bgr',np.uint8).reshape(480,800,3);a=((source.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32);assert (a[:,:,2]|(a[:,:,1]<<8)|(a[:,:,0]<<16)).astype('<u4').tobytes()==live
  result=subprocess.run([str(ROOT/'host/render.exe'),str(p/'live400.u32'),str(p/'result400.u32'),str(p/'boxes400.f32'),str(p/'ui.u32'),str(p/'expected_frame.bgr')],capture_output=True,text=True,check=True);assert 'GUARDS_PASS' in result.stdout and (p/'expected_frame.bgr').read_bytes()==frame
  frames.append(dict(name=p.name,pixels_and_ui_exact=True,stats=s,result_id=u[1],latest_preview_id=u[0]))
 timing={}
 for pl,label in [(0,'cpu'),(1,'fpga')]:
  rows=[]
  for j in range(4):
   m=words(BOARD/f'{label}_timing{j}.bin');mail(m,pl,pipe,mf);assert m[73]==(12 if pl else 0) and m[62]==0
   rows.append(dict(seconds=(m[19]+(m[20]<<32))/m[18],enhancement_span_ms=1000*(m[87]+(m[88]<<32))/m[18],preview_updates=m[70]))
  timing[label]=dict(warmup=rows[0],runs=rows[1:],median_seconds=statistics.median(r['seconds'] for r in rows[1:]))
 write(BOARD/'validated.json',dict(status='NEW_TWILIGHT_MODEL_ALL86_ALL8_AND_LIVE_PHYSICAL_VALIDATED',default_pipe=pipe,first_physical_cpu_pl_heads_decode_nms_byte_exact=True,all86_first=layers,cases=packets,frames=frames,timing=timing,weights_fnv32=mf,hardware_access=True,sd_written=False));print('TWILIGHT_BOARD_ALL_NUMERICS_VIDEO_PASS',timing,flush=True)
if __name__=='__main__':main()
