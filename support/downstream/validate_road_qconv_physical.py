"""Validate integer HW independently against the frozen QAT C outputs."""
from pathlib import Path
import json,statistics,struct,subprocess
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
def words(p):
    raw=Path(p).read_bytes();assert len(raw)==320;return struct.unpack('<80I',raw)
def fnv(raw):
    h=2166136261
    for v in raw:h=((h^v)*16777619)&0xffffffff
    return h
def validate():
    folder=ROOT/'physical_experiment_r1';prep=json.loads((ROOT/'arm_prepared.json').read_text());quant=Path(prep['quant_folder']);g=json.loads((NN/'graph.json').read_text());fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures'];first=fixtures[0]['name']
    assert (folder/'COMPLETE.txt').read_text().strip()=='ROAD_QCONV_FULL_TEST_READBACK_COMPLETE'
    def mail(m,mode,name):
        assert m[0]==0x524F4144 and m[1]==12 and m[2]==3 and m[3]==1 and m[6]==0 and m[57]==1
        assert m[30]==0x7084 and m[40]==0x5640 and m[35]==m[41]==0
        assert m[72]==mode and m[73]==(60 if mode else 0) and m[74]==0 and m[77]==0x5138504B
        assert m[16]==fnv((NN/'cases'/name/'input400.u32').read_bytes()) and m[17]==prep['model_fnv32'] and m[18]>0 and m[62]==0
    def arrays(a,b,label,heads=False):
        assert a.shape==b.shape and np.isfinite(a).all(),label
        d=abs(a-b)
        if heads:assert np.all(d<=2e-5+2e-6*abs(b)),(label,float(d.max()))
        else:assert np.all(d[:,:4]<=.003) and np.all(d[:,4:]<=2e-5),(label,float(d.max()))
        return float(d.max()) if d.size else 0.
    def packet(path,name,mode):
        m=words(path/'mailbox80.bin');mail(m,mode,name);ref=quant/'host'/name;err=[]
        for j,tid in enumerate(g['heads']):err.append(arrays(np.fromfile(path/f'head{j}.f32','<f4'),np.fromfile(ref/'trace'/f'{tid:03d}.f32','<f4'),(name,tid),True))
        arrays(np.fromfile(path/'decoded.f32','<f4').reshape(-1,9),np.fromfile(ref/'decoded.f32','<f4').reshape(-1,9),name)
        a=np.fromfile(path/'boxes400.f32','<f4').reshape(-1,6);b=np.fromfile(ref/'boxes400.f32','<f4').reshape(-1,6);assert a.shape==b.shape
        for c in range(4):
            aa=a[a[:,5]==c];bb=b[b[:,5]==c];assert len(aa)==len(bb)
            for row in aa:
                dist=np.max(abs(bb[:,:4]-row[:4]),axis=1);k=int(dist.argmin());assert dist[k]<.004 and abs(bb[k,4]-row[4])<2e-5;bb=np.delete(bb,k,axis=0)
        return dict(name=name,mode=mode,boxes=len(a),head_max_abs=max(err))
    packets=[packet(folder/'cpu_first',first,0)]+[packet(folder/f['name'],f['name'],1) for f in fixtures]
    full=folder/'first_fpga_full';m=words(full/'mailbox80.bin');mail(m,1,first);raw=(full/'all_layers.f32').read_bytes();off=0
    for t in g['tensors']:
        i=t['id'];size=t['elements']*(4 if i in g['heads'] else 1);a=raw[off:off+size];b=(quant/'host'/first/'trace'/f'{i:03d}.f32').read_bytes();off+=size
        if i in g['heads']:arrays(np.frombuffer(a,'<f4'),np.frombuffer(b,'<f4'),i,True)
        else:assert a==b,('integer codes differ',i)
    assert off==len(raw)==5137600
    live=(full/'live400.u32').read_bytes();result=(full/'result400.u32').read_bytes();frame=(full/'frame.bgr').read_bytes();assert fnv(live)==m[65] and fnv(result)==m[64] and fnv(frame)==m[37]
    assert result==(NN/'cases'/first/'input400.u32').read_bytes()
    src=np.fromfile(full/'capture_source.bgr',np.uint8).reshape(480,800,3);avg=((src.astype(np.uint16).reshape(240,2,400,2,3).sum((1,3))+2)//4).astype(np.uint32)
    assert (avg[:,:,2]|(avg[:,:,1]<<8)|(avg[:,:,0]<<16)).astype('<u4').tobytes()==live
    p=subprocess.run([str(ROOT/'render.exe'),str(full/'live400.u32'),str(full/'result400.u32'),str(full/'boxes400.f32'),str(full/'ui.u32'),str(full/'expected_frame.bgr')],capture_output=True,text=True,check=True);assert 'GUARDS_PASS' in p.stdout and (full/'expected_frame.bgr').read_bytes()==frame
    timing={}
    for mode,label in [(0,'cpu'),(1,'fpga')]:
        runs=[]
        for j in range(4):
            tm=words(folder/f'{label}_timing{j}.bin');mail(tm,mode,first);hz=tm[18]
            runs.append(dict(total_seconds=(tm[19]+(tm[20]<<32))/hz,network_seconds=(tm[21]+(tm[22]<<32))/hz,hardware_call_span_seconds=(tm[75]+(tm[76]<<32))/hz,preview_updates=tm[70]))
        timing[label]=dict(warmup=runs[0],runs=runs[1:],median_total_seconds=statistics.median(r['total_seconds'] for r in runs[1:]))
    live=[]
    for period in [150,100,50]:
        lr=(folder/f'live_{period}ms_mailbox96.bin').read_bytes();assert len(lr)==384;lm=struct.unpack('<96I',lr);assert lm[0]==0x524F4144 and lm[1]==12 and lm[6]==lm[35]==lm[41]==0 and lm[80]>=2 and lm[55]==period
        elapsed=((lm[83]+(lm[84]<<32))-(lm[81]+(lm[82]<<32)))/lm[18];assert elapsed>0 and lm[86]>lm[85] and lm[86]-lm[85]>=lm[80]-1
        live.append(dict(unique_completions=lm[80],completion_interval_seconds=elapsed,unique_detection_fps=(lm[80]-1)/elapsed,first_input_id=lm[85],last_input_id=lm[86],last_visible_result_age_ms=lm[87],preview_period_ms=lm[55],measurement='ARM first/last completed-present timestamps, distinct input snapshot IDs; no JTAG reads inside measured window'))
    proof=dict(status='Q8_EXPERIMENT_PHYSICAL_NUMERICS_VIDEO_AND_TIMING_PASS_NOT_DEFAULT_UPGRADE',all86_integer_codes_exact=True,all8_heads_decode_nms_within_original_quant_tolerance=True,framebuffer_and_capture_exact=True,packets=packets,timing=timing,integer_cpu_vs_fpga_speedup=timing['cpu']['median_total_seconds']/timing['fpga']['median_total_seconds'],accuracy_gate_passed=False,default_promotion_allowed=False,live_unique_frame_fps_measured=True,live=live,sd_written=False)
    (folder/'validated.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2));return proof
if __name__=='__main__':validate()
