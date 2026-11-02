"""Actual portable FP32 C on all672, then C/NumPy fusion equality."""
import concurrent.futures as cf,ctypes as ct,os,shutil,subprocess,time
from road_accuracy_common import *
HERE=Path(__file__).resolve().parent
EXE=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe'
SELECTION_FILE=None
WEIGHTS_FILE=None
EXPECTED_WEIGHTS_SHA=None

def main():
    selection_file=Path(SELECTION_FILE) if SELECTION_FILE else ROOT/'selected.json'
    s=read(selection_file);assert s['qualified'] and s['chosen']['tag']=='three_raw_w75'
    out=ROOT/'native';out.mkdir(exist_ok=True);scratch=out/'scratch';scratch.mkdir(exist_ok=True)
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    build=read(BASE/'road_local_enhance_20261029_r2/host/build.json');assert sha(EXE)==build['exe_sha256']
    weights_file=Path(WEIGHTS_FILE) if WEIGHTS_FILE else APP/'runtime/weights.f32'
    if WEIGHTS_FILE:
        assert EXPECTED_WEIGHTS_SHA and sha(weights_file)==EXPECTED_WEIGHTS_SHA
        identity=dict(weights_sha256=sha(weights_file),manifest_sha256=sha(ROOT/'fresh/manifest.json'),host_exe_sha256=sha(EXE))
        if (out/'run_identity.json').exists():assert read(out/'run_identity.json')==identity,'Cached outputs belong to another model or dataset'
        else:
            assert not (out/'global_raw.json').exists() and not any(out.glob('tile_raw_*.json'))
            write(out/'run_identity.json',identity)
    else:assert sha(weights_file)==build['weights_sha256']
    src=out/'fusion_source';src.mkdir(exist_ok=True)
    for name in ['road_vehicle_multiview.c','road_vehicle_multiview.h']:shutil.copy2(HERE/name,src/name)
    for name in ['road_fp32.h','road_graph.h']:shutil.copy2(APP/'source'/name,src/name)
    cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-shared','-static-libgcc','-Wl,--export-all-symbols',str(src/'road_vehicle_multiview.c'),'-lm','-o',str(out/'fusion.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'fusion_build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    views={k:[] for k in ['global_raw','tile_raw_0','tile_raw_1','tile_raw_2']};rawtiles={k:[] for k in views if k.startswith('tile')}
    manifest=read(ROOT/'fresh/manifest.json');rows=[dict(name=r['name'],timeofday=r['timeofday'],ground_truth=truth(ROOT/'fresh/labels'/(Path(r['name']).stem+'.txt')).tolist()) for r in manifest]
    begin=time.monotonic()
    def one(task):
        at,r,tag=task;sensor,full=sensor400(ROOT/'fresh/images'/r['name'])
        im=full if tag=='global_raw' else sensor[120:360,int(tag[-1])*200:int(tag[-1])*200+400]
        folder=scratch/(tag+'_'+str(at));folder.mkdir();a=im.astype(np.uint32);ip=folder/'input.u32';(a[:,:,0]|a[:,:,1]<<8|a[:,:,2]<<16).astype('<u4').tofile(ip)
        p=subprocess.run([str(EXE),str(weights_file),str(ip),str(folder)],capture_output=True,text=True,env=env,timeout=90)
        assert p.returncode==0 and 'ROAD_FP32_HOST_DONE' in p.stdout,(r['name'],tag,p.stdout,p.stderr)
        pred=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);assert np.isfinite(pred).all()
        for f in folder.iterdir():assert f.resolve().is_relative_to(scratch.resolve()) and f.is_file();f.unlink()
        folder.rmdir();return pred
    for tag in views:
        cache=out/(tag+'.json');localcache=out/(tag+'_local.json')
        if cache.exists():
            views[tag]=read(cache)
            if tag in rawtiles:rawtiles[tag]=read(localcache)
            continue
        with cf.ThreadPoolExecutor(2) as pool:
            for at,pred in enumerate(pool.map(one,[(i,r,tag) for i,r in enumerate(rows)])):
                if tag in rawtiles:rawtiles[tag].append(pred.tolist());mapped=map_tile(pred,*TILES[int(tag[-1])])
                else:mapped=pred
                views[tag].append(dict(**rows[at],detections=mapped.tolist()))
                if (at+1)%48==0:print('ACCURACY_ACTUAL_C',tag,at+1,len(rows),round(time.monotonic()-begin),flush=True)
        write(cache,views[tag])
        if tag in rawtiles:write(localcache,rawtiles[tag])
    lib=ct.CDLL(str(out/'fusion.dll'))
    class Box(ct.Structure):_fields_=[(k,ct.c_float) for k in ['x1','y1','x2','y2','score']]+[('cls',ct.c_int),('order',ct.c_int)]
    fn=lib.road_vehicle_multiview;fn.argtypes=[ct.POINTER(Box),ct.c_int,ct.POINTER(Box),ct.POINTER(ct.c_int),ct.c_float,ct.POINTER(Box),ct.c_int];fn.restype=ct.c_int
    def fill(buf,values,offset=0):
        for j,p in enumerate(values):buf[offset+j]=Box(*map(float,p[:5]),int(p[5]),j)
    fused=[];maxdiff=0.
    for at,r in enumerate(rows):
        full=views['global_raw'][at]['detections'];tiles=[views['tile_raw_'+str(i)][at]['detections'] for i in range(3)];reference=fuse(full,tiles,.75)
        a=(Box*300)();b=(Box*900)();dest=(Box*302)();counts=(ct.c_int*3)(*[len(rawtiles['tile_raw_'+str(i)][at]) for i in range(3)])
        fill(a,full)
        for i in range(3):fill(b,rawtiles['tile_raw_'+str(i)][at],i*300)
        dest[0].order=0x12345678;dest[301].order=0x12345678
        resultptr=ct.cast(ct.byref(dest,ct.sizeof(Box)),ct.POINTER(Box));n=fn(a,len(full),b,counts,.75,resultptr,300)
        assert 0<=n<=300 and dest[0].order==dest[301].order==0x12345678
        actual=np.array([[dest[i+1].x1,dest[i+1].y1,dest[i+1].x2,dest[i+1].y2,dest[i+1].score,dest[i+1].cls] for i in range(n)],np.float32).reshape(-1,6)
        assert actual.shape==reference.shape and actual.tobytes()==reference.tobytes(),(r['name'],actual.shape,reference.shape)
        fused.append(dict(**r,detections=actual.tolist()))
    scores=dict(baseline=metrics(views['global_raw']),candidate=metrics(fused))
    write(out/'baseline_predictions.json',views['global_raw']);write(out/'candidate_predictions.json',fused)
    for tag,m in scores.items():write(out/(tag+'_metrics.json'),m)
    write(out/'complete.json',dict(status=f'ALL{len(rows)}_ACTUAL_C_FP32_AND_MULTIVIEW_FUSION_BYTE_EXACT',images=len(rows),all_c_fusion_byte_exact=True,output_guards_pass=True,scores=scores,weights_sha256=sha(weights_file),host_exe_sha256=sha(EXE),fusion_source_sha256=sha(src/'road_vehicle_multiview.c'),fusion_compiler=cmd,baseline_selection_file=str(selection_file),selection_sha256=sha(selection_file),seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
    summary_period=next(iter(scores['baseline']['by_time']))
    print('ACCURACY_ALL_ACTUAL_C_COMPLETE',len(rows),summary_period,scores['baseline']['by_time'][summary_period]['classes']['car'],scores['candidate']['by_time'][summary_period]['classes']['car'],flush=True)

if __name__=='__main__':main()
