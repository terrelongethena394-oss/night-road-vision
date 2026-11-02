"""Shared16-lane candidate: RTL and routing parallel, strict gates before JTAG."""
import subprocess,sys,time,csv
from pathlib import Path
from conv13_p16_config import HLS,RUNTIME,PACKAGE,BOARD,configure_build
from prepare_fp32_cpu_pack import HERE,read,write
HLS_EXE='E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat'

def main():
    deadline=time.monotonic()+3600
    while 'ROAD_CONV3_SYNTH_COMPLETE_P16' not in (HLS/'synth.log').read_text(errors='replace'):
        assert time.monotonic()<deadline;time.sleep(3)
    assert len(list(csv.DictReader((HLS/'tb_csim.csv').open())))==60
    with (RUNTIME/'package_board_console.log').open('w') as f:
        worker=subprocess.Popen([sys.executable,str(HERE/'package_build_conv13_p16.py')],stdout=f,stderr=subprocess.STDOUT)
        while not (PACKAGE/'copy_frozen.json').exists():
            assert worker.poll() is None and time.monotonic()<deadline,'Snapshot copy failed';time.sleep(2)
        with (HLS/'cosim.log').open('w') as log:
            p=subprocess.run([HLS_EXE,'-f',str(HLS/'cosim.tcl')],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        assert 'ROAD_CONV3_COSIM_COMPLETE_P16' in (HLS/'cosim.log').read_text(errors='replace'),'P16 RTL gate incomplete'
        assert worker.wait(timeout=2400)==0,'P16 routed build gate failed'
    b=configure_build();b.finish_hls(read(PACKAGE/'snapshot.json')['ip']);b.finalize()
    import compile_road_conv13_runtime as c
    c.ROOT=RUNTIME;c.HLS=HLS;c.BOARD=BOARD;c.VERSION=18;c.PE=16;c.SELECT_BEST_POLICY=True;c.main()
    import prepare_conv13_acceptance as a
    a.ROOT=RUNTIME;a.VERSION=18;a.SELECT_BEST_POLICY=True;a.main()
    compile((RUNTIME/'run_acceptance.py').read_text(encoding='utf-8'),str(RUNTIME/'run_acceptance.py'),'exec')
    assert read(RUNTIME/'original_baseline.json')['status']=='ACTUAL_ABI15_MEASURED_CAMERA_RESUMED'
    with (RUNTIME/'acceptance_console.log').open('w') as f:p=subprocess.run([sys.executable,str(RUNTIME/'run_acceptance.py')],stdout=f,stderr=subprocess.STDOUT,timeout=2600)
    state=read(RUNTIME/'session.json')
    if state['status']=='CONV13_BYTE_EXACT_FASTER_VALIDATED_AND_LIVE':
        import confirm_conv13_speed as confirm
        confirm.ROOT=RUNTIME;confirm.APP=RUNTIME/'firmware';confirm.VERSION=18;confirm.SELECT_BEST_POLICY=True;confirm.main()
    else:assert state['status']=='NOT_PROMOTED_PREVIOUS_ABI15_RESTORED' and state['restored'],state

if __name__=='__main__':main()
