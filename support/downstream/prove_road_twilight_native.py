"""Independent primitive lowering and actual C proof before any board update."""
from pathlib import Path
import importlib.util,json,os,shutil,subprocess,sys,types
import cv2,numpy as np
from road_twilight_common import ROOT,BASE,NN,read,write,sha
from road_arm_common import preprocess400
from road_enhance_common import enhance
from export_road_twilight_weights import pack
HERE=Path(__file__).resolve().parent
def prove(root,checkpoint,pipe,tag='native_candidate'):
 root=Path(root);checkpoint=Path(checkpoint);out=root/tag;out.mkdir(exist_ok=False);model,g,weights,shapes=pack(checkpoint);weights.tofile(out/'weights.f32')
 assert pipe in [1,2];shutil.copy2(NN/'road_graph.h',out/'road_graph.h')
 spec=importlib.util.spec_from_file_location('original_lowering',HERE/'export_road_arm.py');lower=importlib.util.module_from_spec(spec);spec.loader.exec_module(lower)
 import torch
 from utils.general import non_max_suppression,scale_boxes
 from verify_road_arm_host import compare_boxes
 torch.set_num_threads(4)
 # Examples are metadata order, not chosen by model success.
 selection=read(root/'fresh_selection.json');cases=[]
 for period in ['night','dawn/dusk','daytime']:
  for r in [r for r in selection if r['timeofday']==period][:2]:cases.append(dict(name=Path(r['name']).stem,source=r['name'],timeofday=period,kind='real'))
 cases.extend([dict(name='control_black',kind='synthetic'),dict(name='control_random',kind='synthetic')])
 write(out/'protocol.json',dict(status='FROZEN_BEFORE_C_AND_LOWERED_FIXTURE_FORWARD',checkpoint_sha256=sha(checkpoint),weights_sha256=sha(out/'weights.f32'),pipe_mode=pipe,cases=cases,selection_rule='First2 per time group in previously frozen metadata, plus black and seeded random controls.',tolerance='Original FP32 contract: all86 1e-4+1e-4*abs(ref); decoded coordinates.02/scores2e-4; mapped boxes.04.',hardware_access=False))
 src=out/'source';src.mkdir()
 for n in ['road_fp32.c','road_fp32.h','road_graph.h']:shutil.copy2(NN/'source_r2'/n,src/n)
 shutil.copy2(HERE/'road_fp32_host.c',src/'road_fp32_host.c')
 gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+';'+env['PATH']
 cmd=[str(gcc),'-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(src),str(src/'road_fp32.c'),str(src/'road_fp32_host.c'),'-lm','-o',str(out/'host.exe')]
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
 from prepare_road_light import sensor_proxy
 rng=np.random.default_rng(2026102747);records=[]
 with torch.inference_mode():
  for r in cases:
   folder=out/'cases'/r['name'];folder.mkdir(parents=True);gold=folder/'gold';gold.mkdir();host=folder/'host';host.mkdir();trace=host/'trace';trace.mkdir()
   if r['kind']=='real':raw=sensor_proxy(cv2.imread(str(root/'fresh/images'/r['source']))[:,:,::-1].copy())
   elif r['name']=='control_black':raw=np.zeros((240,400,3),np.uint8)
   else:raw=rng.integers(0,256,(240,400,3),np.uint8)
   enhanced,stats=enhance(raw,1,32);effective=enhanced if pipe==1 else raw
   for label,a in [('input400.u32',raw),('enhanced400.u32',enhanced),('effective400.u32',effective)]:
    w=a[:,:,0].astype(np.uint32)|(a[:,:,1].astype(np.uint32)<<8)|(a[:,:,2].astype(np.uint32)<<16);w.astype('<u4').tofile(folder/label)
   prepared=preprocess400(effective);prepared.tofile(folder/'input320.rgb');x=torch.from_numpy(prepared.transpose(2,0,1).copy())[None].float()/255
   decoded,heads=model(x);vals=lower.execute(types.SimpleNamespace(ops=g['tensors'][1:]),weights,x)
   for j,tid in enumerate(g['heads']):
    t=g['tensors'][tid];z=vals[tid].reshape(1,3,9,t['h'],t['w']).permute(0,1,3,4,2);assert torch.equal(z,heads[j]),(r['name'],tid)
   for t in g['tensors']:
    v=vals[t['id']][0].permute(1,2,0).numpy();a=np.zeros((t['h'],t['w'],t['c4']),'<f4');a[:,:,:t['c']]=v;a.tofile(gold/f'{t["id"]:03d}.f32')
   decoded.numpy().astype('<f4').tofile(gold/'decoded.f32');boxes=non_max_suppression(decoded.clone(),.25,.6,max_det=300)[0]
   if len(boxes):scale_boxes((320,320),boxes[:,:4],(240,400),ratio_pad=((.8,.8),(0.,64.)))
   boxes.numpy().astype('<f4').tofile(gold/'boxes400.f32')
   p=subprocess.run([str(out/'host.exe'),str(out/'weights.f32'),str(folder/'effective400.u32'),str(host),str(trace)],capture_output=True,text=True,env=env);assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,p.stderr
   assert (host/'input320.rgb').read_bytes()==prepared.tobytes();errors=[]
   for t in g['tensors']:
    a=np.fromfile(trace/f'{t["id"]:03d}.f32','<f4');b=np.fromfile(gold/f'{t["id"]:03d}.f32','<f4');assert a.shape==b.shape and np.isfinite(a).all();d=abs(a-b);assert np.all(d<=1e-4+1e-4*abs(b)),(r['name'],t['id'],float(d.max()));errors.append(float(d.max(initial=0)))
   a=np.fromfile(host/'decoded.f32','<f4').reshape(-1,9);b=np.fromfile(gold/'decoded.f32','<f4').reshape(-1,9);d=abs(a-b);assert d[:,:4].max()<=.02 and d[:,4:].max()<=2e-4
   bx=compare_boxes(np.fromfile(host/'boxes400.f32','<f4').reshape(-1,6),boxes.numpy(),.04)
   records.append(dict(**r,input_sha256=sha(folder/'input400.u32'),enhancement_stats=stats,all86_max_abs=max(errors),boxes=bx));print('TWILIGHT_NATIVE_ALL86_PASS',r['name'],max(errors),bx['count'],flush=True)
 write(out/'complete.json',dict(status='NEW_WEIGHTS_ALL60_LAYOUT_AND_ALL8_ALL86_NATIVE_C_PROVEN',checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),weights_sha256=sha(out/'weights.f32'),pipe_mode=pipe,cases=records,shapes=shapes,compiler_command=cmd,hardware_access=False,sd_written=False));return out
def main():
 fresh=read(ROOT/'fresh_complete.json');assert fresh['deployment_decision']!='retain_current'
 sel=read(ROOT/'selected.json');pipe=1 if fresh['deployment_decision']=='enhanced_input' else 2;chosen=sel['candidate'] if pipe==1 else sel['control'];assert sha(chosen['weights'])==chosen['sha256'];prove(ROOT,chosen['weights'],pipe)
if __name__=='__main__':main()
