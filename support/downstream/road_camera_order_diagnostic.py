"""Validation addendum matching current capture quantization/downsample ORDER.

Dataset camera/ISP/exposure are not simulated. No test access or board writes.
"""
from pathlib import Path
import concurrent.futures as cf,os,subprocess,time
import cv2,numpy as np
from road_adapt_common import BASE,ROOT as ROUND2,REF,REF_SHA,read,write,sha,luma
from road_pipeline_diagnose import ROOT,load_float
HERE=Path(__file__).resolve().parent
OUT=ROOT/'camera_order';APP=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026/app_src/main.c')
RTL=Path('E:/FPGA_Enhance_Work/camera_lcd_20261017/prj/camera_lcd.gen/sources_1/bd/system/ipshared/c651/src/ov5640_capture_data.v')
def box(a):
    assert a.dtype==np.uint8 and a.shape==(480,800,3)
    b=a.astype(np.uint16)
    return ((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
def proof():
    folder=OUT/'arithmetic_proof';folder.mkdir()
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');exe=folder/'box.exe'
    env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    subprocess.run([str(gcc),'-O2','-std=c99',str(HERE/'camera_box_reference.c'),'-o',str(exe)],check=True,env=env)
    rng=np.random.default_rng(2026102631);count=0
    for name,a in [('random',rng.integers(0,256,(480,800,3),dtype=np.uint8)),('white',np.full((480,800,3),255,np.uint8)),('black',np.zeros((480,800,3),np.uint8))]:
        ip=folder/(name+'.rgb');op=folder/(name+'.out.rgb');ip.write_bytes(a.tobytes())
        p=subprocess.run([str(exe),str(ip),str(op)],capture_output=True,text=True,check=True)
        assert 'CAMERA_BOX_HOST_DONE' in p.stdout and op.read_bytes()==box(a).tobytes();count+=400*240*3
    write(folder/'complete.json',dict(status='HOST_C_NUMPY_CAMERA_BOX_BYTES_EXACT',bytes=count,cases=3,app_source_sha256=sha(APP),
          source_sha256=sha(HERE/'camera_box_reference.c'),real_board_run=False))
def main():
    assert read(ROOT/'complete.json')['no_test_split_used'];OUT.mkdir(exist_ok=False);start=time.monotonic()
    rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROUND2/'paired_manifest.json') if r['split']=='val']
    protocol=dict(status='FROZEN_BEFORE_CAMERA_ORDER_VIEW_INFERENCE',images=320,split='Old validation only',
         views=['sim888','sim565','sim_float888','sim_float565','sim_fixed565'],detector='previous frozen road4_best.pt at416',
         app_source=str(APP),app_source_sha256=sha(APP),capture_rtl=str(RTL),capture_rtl_sha256=sha(RTL),
         camera_order='Decode BDD RGB, INTER_LINEAR to800x480 as proxy sensor RGB; optional RGB565 zero-extension; average2x2 with(sum+2)//4; enhance400x240.',
         limitation='Preprocessing-order simulation only. BDD sensor ISP, exposure, demosaicing, camera response and on-board captures are NOT recreated.',
         parent_protocol_sha256=sha(ROOT/'protocol.json'),no_test_used=True,weights_changed=False,board_modified=False,sd_written=False)
    assert sha(REF)==REF_SHA;write(OUT/'protocol.json',protocol);proof()
    import torch
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    original,_=load_float();original=original.cuda();frames=OUT/'frames';frames.mkdir();temp=OUT/'reference_inputs';temp.mkdir();stats=[]
    def prepare(r):
        rgb=cv2.imread(str(BASE/'dataset/images/val'/r['name']))[:,:,::-1];a=cv2.resize(rgb,(800,480),interpolation=cv2.INTER_LINEAR)
        q=a.copy();q[:,:,0]&=248;q[:,:,1]&=252;q[:,:,2]&=248;raw888=box(a);raw565=box(q);stem=Path(r['name']).stem
        ip=temp/(stem+'.rgb');op=temp/(stem+'.fixed.rgb');ip.write_bytes(raw565.tobytes())
        p=subprocess.run([str(REF),str(ip),'240','400',str(op)],capture_output=True,text=True,check=True);assert 'MULTINEX_CPP_DONE' in p.stdout
        fixed=np.fromfile(op,np.uint8).reshape(240,400,3)
        return r,raw888,raw565,fixed
    def infer(a):
        x=torch.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).cuda().float()[None]/255
        with torch.inference_mode():v=original(x)[0].permute(1,2,0).cpu().numpy()
        return np.floor(np.clip(v,0,1)*255+.5).astype(np.uint8)
    with cf.ThreadPoolExecutor(4) as pool:
        for i,(r,a,b,c) in enumerate(pool.map(prepare,rows),1):
            d=dict(sim888=a,sim565=b,sim_fixed565=c,sim_float888=infer(a),sim_float565=infer(b));stem=Path(r['name']).stem
            item=dict(name=r['name'],timeofday=r['timeofday'],views={},pairs={})
            for kind,image in d.items():
                assert cv2.imwrite(str(frames/(stem+'.'+kind+'.png')),image[:,:,::-1])
                item['views'][kind]=dict(mean_luma=float(luma(image).mean()),zero_pixel_fraction=float((image.max(2)==0).mean()),all_channel_255_fraction=float((image.min(2)==255).mean()))
            for x,y in [('sim565','sim888'),('sim_fixed565','sim_float565'),('sim_float565','sim_float888')]:
                diff=np.abs(d[x].astype(np.int16)-d[y].astype(np.int16));item['pairs'][x+'__'+y]=dict(mae=float(diff.mean()),max_abs=int(diff.max()))
            stats.append(item)
            if i%40==0:print('CAMERA_ORDER_VIEWS_READY',i,flush=True)
    del original;torch.cuda.empty_cache();write(OUT/'pixel_diagnostics.json',stats)
    from road_pipeline_eval import PipelineEvaluator
    evaluator=PipelineEvaluator(BASE/'frozen/road4_best.pt');scores={}
    for view in protocol['views']:
        scores[view]=evaluator.run(rows,lambda r,k=view:cv2.imread(str(frames/(Path(r['name']).stem+'.'+k+'.png')))[:,:,::-1].copy(),OUT,view)
    evaluator.close();write(OUT/'complete.json',dict(status='CAMERA_PREPROCESS_ORDER_VALIDATION_ADDENDUM_COMPLETE',scores=scores,seconds=time.monotonic()-start,
           no_new_test=True,no_board_run=True,sd_written=False,protocol_sha256=sha(OUT/'protocol.json')))
    print('CAMERA_ORDER_DIAGNOSTIC_COMPLETE',flush=True)
if __name__=='__main__':main()
