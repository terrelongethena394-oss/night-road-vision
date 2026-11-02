"""Check actual enhanced pixels, detector input, all86 first tensors and display."""
from pathlib import Path
import json,statistics,struct,subprocess
import numpy as np
from road_enhance_common import ROOT,NN,OLD,enhance,sha,write
from road_arm_common import preprocess400
from verify_road_arm_host import compare_boxes
APP=ROOT/'firmware';BOARD=APP/'board_fixed_r1'
def words(p):
 b=Path(p).read_bytes();assert len(b)==384;return struct.unpack('<96I',b)
def fnv(b):
 h=2166136261
 for x in b:h=((h^x)*16777619)&0xffffffff
 return h
def image_words(b):
 w=np.frombuffer(b,'<u4').reshape(240,400);return np.stack([w&255,(w>>8)&255,(w>>16)&255],2).astype(np.uint8)
def check_mail(m,mode=None):
 assert m[0]==0x524f4144 and m[1]==13 and m[2]==3 and m[3]==1 and m[6]==0 and m[57]==1
 assert m[30]==0x7084 and m[40]==0x5640 and m[35]==m[41]==0 and m[72]==1 and m[74]==0 and m[77]==0x5041434b
 if mode is not None:assert m[80]==mode and m[73]==12 and m[62]==0
def enhanced_pair(raw_bytes,enh_bytes,mode,cap):
 raw=image_words(raw_bytes);actual=image_words(enh_bytes);expected,stats=enhance(raw,0 if mode==0 else 1,cap);assert np.array_equal(actual,expected)
 return expected,stats
def floats(a,b,label,kind='head'):
 assert a.shape==b.shape and np.isfinite(a).all(),label;d=abs(a-b)
 if kind=='decode':assert d[:,:4].max()<=.02 and d[:,4:].max()<=2e-4,(label,float(d.max()))
 else:assert np.all(d<=1e-4+1e-4*abs(b)),(label,float(d.max()))
 return float(d.max(initial=0))
def packet(path,name,mode,full=False):
 m=words(path/('mailbox.bin' if full else 'mailbox96.bin'));check_mail(m,mode)
 raw=(path/'raw_result400.u32').read_bytes();enh=(path/('result400.u32' if full else 'enhanced400.u32')).read_bytes();expected,stats=enhanced_pair(raw,enh,mode,m[81])
 assert raw==(NN/'cases'/name/'input400.u32').read_bytes();assert m[16]==fnv(raw) and m[17]==1483844061
 assert m[82:87]==tuple(stats[k] for k in ['mean_in','mean_out','alpha','changed','max_delta'])
 assert (path/'preprocessed.rgb').read_bytes()==preprocess400(expected if mode==1 else image_words(raw)).tobytes()
 ref=ROOT/'host'/name if mode==1 else NN/'host_r2'/name;g=json.loads((NN/'graph.json').read_text());head_errors=[]
 for j,tid in enumerate(g['heads']):head_errors.append(floats(np.fromfile(path/f'head{j}.f32','<f4'),np.fromfile(ref/'trace'/f'{tid:03d}.f32','<f4'),(name,j)))
 floats(np.fromfile(path/'decoded.f32','<f4').reshape(-1,9),np.fromfile(ref/'decoded.f32','<f4').reshape(-1,9),name,'decode')
 box=compare_boxes(np.fromfile(path/'boxes400.f32','<f4').reshape(-1,6),np.fromfile(ref/'boxes400.f32','<f4').reshape(-1,6),.04)
 return dict(name=name,mode=mode,stats=stats,enhanced_rgb_bytes_exact=True,preprocessing_bytes_exact=True,head_max_abs=max(head_errors),boxes=box)
def frame(path):
 m=words(path/'mailbox.bin');check_mail(m);ui=struct.unpack('<15I',(path/'ui.u32').read_bytes());raw=(path/'raw_result400.u32').read_bytes();enh=(path/'result400.u32').read_bytes();live=(path/'live400.u32').read_bytes();pixels=(path/'frame.bgr').read_bytes()
 expected,stats=enhanced_pair(raw,enh,ui[14],ui[13]);assert ui[11]==stats['mean_in'] and ui[12]==stats['alpha'] and ui[14]==m[93]
 assert m[91]==fnv(raw) and m[92]==m[64]==fnv(enh) and m[65]==fnv(live) and m[37]==fnv(pixels)
 src=np.fromfile(path/'capture_source.bgr',np.uint8).reshape(480,800,3);a=((src.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32)
 assert (a[:,:,2]|(a[:,:,1]<<8)|(a[:,:,0]<<16)).astype('<u4').tobytes()==live
 p=subprocess.run([str(ROOT/'host/render.exe'),str(path/'live400.u32'),str(path/'result400.u32'),str(path/'boxes400.f32'),str(path/'ui.u32'),str(path/'expected_frame.bgr')],capture_output=True,text=True,check=True)
 assert 'GUARDS_PASS' in p.stdout and (path/'expected_frame.bgr').read_bytes()==pixels
 return dict(enhanced_pixels_exact=True,raw_and_enhanced_same_result_snapshot=True,capture_and_framebuffer_bytes_exact=True,ui_stats=stats,result_id=ui[1],latest_preview_id=ui[0])
def main():
 assert (BOARD/'COMPLETE.txt').read_text().strip()=='ROAD_ENHANCE_FULL_TEST_READBACK_COMPLETE'
 fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures'];first=fixtures[0]['name'];cap=json.loads((ROOT/'selected.json').read_text())['cap']
 packets=[packet(BOARD/'raw_first',first,0,True),packet(BOARD/'input_first',first,1,True)]+[packet(BOARD/f['name'],f['name'],2) for f in fixtures]
 full=BOARD/'first_view_full';packet(full,first,2,True);raw=(full/'all_layers.f32').read_bytes();off=0;layers=[]
 original=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1/physical_full_r1/first_hybrid_full/all_layers.f32');assert raw==original.read_bytes(),'Default display enhancement must leave all86 detector tensors byte-identical'
 for t in json.loads((NN/'graph.json').read_text())['tensors']:
  n=t['elements']*4;a=np.frombuffer(raw[off:off+n],'<f4');b=np.fromfile(NN/'host_r2'/first/'trace'/f'{t["id"]:03d}.f32','<f4');off+=n;err=floats(a,b,t['id']);layers.append(dict(id=t['id'],max_abs=err))
 assert off==len(raw)==19844800
 frames=[frame(full),frame(BOARD/'live_auto')];timing={}
 for mode,label in [(0,'raw'),(1,'input'),(2,'view')]:
  vals=[]
  for j in range(4):
   m=words(BOARD/f'{label}_timing{j}.bin');check_mail(m,mode);assert m[81]==cap and m[70]>0
   vals.append(dict(processing_seconds=(m[19]+(m[20]<<32))/m[18],enhancement_span_ms=1000*(m[87]+(m[88]<<32))/m[18],preview_updates=m[70]))
  timing[label]=dict(warmup=vals[0],runs=vals[1:],median_seconds=statistics.median(v['processing_seconds'] for v in vals[1:]),median_enhancement_span_ms=statistics.median(v['enhancement_span_ms'] for v in vals[1:]))
 proof=dict(status='ENHANCED_VIEW_WITH_RAW_DETECTOR_ALL86_BYTES_EXACT_AND_LIVE_VIDEO_PASS',default_mode=2,enhanced_detector_input_experiment_first_photo_passed=True,default_view_all86_bytes_exact_to_original_arm=True,selected_cap=cap,enhancement_processor='ARM',neural_enhancement=False,detector_weights_and_bit_unchanged=True,first_all86=layers,packets=packets,frame_checks=frames,timing=timing,hardware_access=True,sd_written=False)
 write(BOARD/'validated.json',proof);print('ROAD_ENHANCE_PHYSICAL_ALL_CHECKS_PASS',timing,flush=True)
if __name__=='__main__':main()
