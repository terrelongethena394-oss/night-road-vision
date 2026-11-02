"""Continue serialized hardware gates and authorized RAM validation in this turn."""
import time,subprocess,sys
from prepare_road_conv13 import ROOT as HLS
from prepare_road_conv13_runtime import ROOT
from prepare_fp32_cpu_pack import BASE,read,write

def main():
    deadline=time.monotonic()+3600
    while 'ROAD_CONV3_COSIM_COMPLETE_P8' not in (HLS/'cosim.log').read_text(errors='replace'):
        assert time.monotonic()<deadline,'RTL simulation still incomplete; preserve current run for diagnosis'
        time.sleep(5)
    import build_road_conv13 as build
    while not (build.ROOT/'offline_complete.json').exists():
        assert time.monotonic()<deadline,'Parallel offline build still incomplete'
        time.sleep(5)
    snapshot=read(BASE/'road_conv13_package_20261028_r1/snapshot.json')
    build.finish_hls(snapshot['ip'])
    build.finalize()
    import compile_road_conv13_runtime as compile_runtime
    compile_runtime.main()
    assert read(ROOT/'original_baseline.json')['status']=='ACTUAL_ABI15_MEASURED_CAMERA_RESUMED'
    with (ROOT/'acceptance_console.log').open('w') as f:p=subprocess.run([sys.executable,str(ROOT/'run_acceptance.py')],stdout=f,stderr=subprocess.STDOUT,timeout=2600)
    state=read(ROOT/'session.json')
    if state['status']=='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE':
        import confirm_conv13_speed
        confirm_conv13_speed.main()
    else:
        assert state['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and state['restored']
        print('CONV13_NOT_PROMOTED_ABI15_RESTORED',flush=True)

if __name__=='__main__':main()
