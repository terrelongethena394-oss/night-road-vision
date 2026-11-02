"""Freeze representative board fixtures plus a labelled illustrative success."""
import ctypes as ct,os,subprocess,sys,shutil
from PIL import Image
from road_accuracy_common import *
APP=ROOT/'firmware'

def fnv(data):
    v=2166136261
    for b in data:v=((v^b)*16777619)&0xffffffff
    return v
def words(a,p):
    b=a.astype(np.uint32);(b[:,:,0]|b[:,:,1]<<8|b[:,:,2]<<16).astype('<u4').tofile(p)
def main():
    assert read(ROOT/'fresh_result.json')['quality_accepted']
    if (APP/'cases.json').exists():
        assert '--revise-display-example' in sys.argv or '--revise-brightness-example' in sys.argv
        if '--revise-brightness-example' in sys.argv:
            assert not (ROOT/'rejected_bright_display_fixture.json').exists()
            shutil.copy2(ROOT/'board_fixture_protocol.json',ROOT/'rejected_bright_display_fixture.json')
        elif (ROOT/'initial_board_fixture_protocol.json').exists():
            assert sha(ROOT/'initial_board_fixture_protocol.json')==sha(ROOT/'board_fixture_protocol.json')
        else:
            shutil.copy2(ROOT/'board_fixture_protocol.json',ROOT/'initial_board_fixture_protocol.json')
            shutil.copy2(APP/'cases.json',ROOT/'initial_board_cases.json')
    rows=read(ROOT/'fresh/manifest.json');changes=read(ROOT/'changes_all672.json');chosen=[]
    chosen += [r for r in rows if r['timeofday']=='night'][:2]
    chosen += [r for r in rows if r['timeofday']=='dawn/dusk'][:1]
    chosen += [r for r in rows if r['timeofday']=='daytime'][:1]
    brightness={r['name']:r['mean_y'] for r in read(ROOT/'brightness_audit.json')['rows']} if (ROOT/'brightness_audit.json').exists() else {}
    illustrative_pool=[r for r in changes if r['timeofday']=='night' and brightness.get(r['name'],0)<=48 and len(r['recovered_car_gt_indices'])>=2 and not r['lost_car_gt_indices'] and r['candidate_car_fp']<=r['baseline_car_fp']]
    illustrative=min(illustrative_pool,key=lambda r:(r['candidate_car_fp'],-len(r['recovered_car_gt_indices']),r['name'])) if illustrative_pool else None
    if illustrative and illustrative['name'] not in {r['name'] for r in chosen}:chosen.append(next(r for r in rows if r['name']==illustrative['name']))
    cases=[]
    proof=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');lib=ct.CDLL(str(Path(proof['attempt'])/'retinex.dll'))
    class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
    ptr=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float);lib.road_retinex_c.argtypes=[ptr,ptr,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
    for index,r in enumerate(chosen+[dict(name='control_black',timeofday='control')]):
        name=Path(r['name']).stem;folder=APP/'runtime/cases'/name;folder.mkdir(parents=True,exist_ok=any(v.startswith('--revise-') for v in sys.argv))
        sensor,full=sensor400(ROOT/'fresh/images'/r['name']) if r['name']!='control_black' else (np.zeros((480,800,3),np.uint8),np.zeros((240,400,3),np.uint8))
        Image.fromarray(sensor).save(folder/'sensor800.png');Image.fromarray(full).save(folder/'raw.png');words(full,folder/'input400.u32')
        raw=np.fromfile(folder/'input400.u32','<u4');dest=np.empty_like(raw);work=np.empty(17*96000+65536,np.float32);stats=Stats()
        assert lib.road_retinex_c(raw.ctypes.data_as(ptr),dest.ctypes.data_as(ptr),96000,work.ctypes.data_as(fp),ct.byref(stats),None,None)==0
        dest.tofile(folder/'enhanced400.u32');views=[]
        for vi in range(4):
            view=folder if vi==0 else folder/('tile'+str(vi-1));view.mkdir(exist_ok=True)
            if vi:words(sensor[120:360,(vi-1)*200:(vi-1)*200+400],view/'input400.u32')
            views.append(dict(id=name+('' if vi==0 else '/tile'+str(vi-1)),view=vi,expected_fnv=fnv((view/'input400.u32').read_bytes()),input_sha256=sha(view/'input400.u32')))
        cases.append(dict(name=name,original_name=r['name'],photo=index+1,timeofday=r['timeofday'],views=views,illustrative=bool(illustrative and r['name']==illustrative['name']),fixture_selection='First2 night-labelled,first dusk-labelled,first daytime-labelled; plus illustrative meanY<=48, >=2 recovered cars, no lost cars and no additional car FP, ranked by fewest FP then most recovered cars. After visual review, daytime-looking night-labelled example removed. Display-only revision; no model/threshold/accuracy changes. Black control. Not used for accuracy statistics.'))
    write(APP/'cases.json',cases);write(ROOT/'board_fixture_protocol.json',dict(cases=cases,illustration_does_not_define_accuracy=True,accuracy_source='All672 including all failures',default_case=next((r['name'] for r in cases if r['illustrative']),cases[0]['name']),fresh_result_sha256=sha(ROOT/'fresh_result.json'),hardware_access=False,sd_written=False))
    # Build portable decoder/postprocessing DLL to process authentic ARM logits.
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    src=BASE/'road_arm_prototype_20261026/source_r2';dest=APP/'host/post.dll'
    cmd=[str(gcc),'-O3','-std=c99','-fno-fast-math','-ffp-contract=off','-shared','-static-libgcc','-Wl,--export-all-symbols','-I'+str(src),str(src/'road_fp32.c'),'-lm','-o',str(dest)]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
    write(ROOT/'board_numerical_gates.json',dict(neural='Each of4 decoded tensors byte-exact to actual ABI22 running the same input on the same PL core; not native x86 float patterns.',postprocessing='C fused operating-point boxes byte-exact using actual ABI22 logits and portable C NMS/fusion independently proven against NumPy on all672.',enhancement='Byte-exact to unchanged ABI22 C implementation',display='Byte-exact to independent host renderer with guard bytes',pl_calls=204,no_sd=True))
    write(APP/'runtime_checksums.json',{str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']})
    print('ACCURACY_BOARD_FIXTURES_READY',[(r['name'],r['illustrative']) for r in cases],flush=True)

if __name__=='__main__':main()
