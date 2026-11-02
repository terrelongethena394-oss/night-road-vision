"""Read-only check that the final accepted17/mode2 camera keeps progressing."""
import subprocess,struct
from prepare_fp32_cpu_pack import read,write
from prepare_road_conv13_runtime import ROOT
VERSION=17
MODE=2

def main():
    assert read(ROOT/'alternating_speed.json')['status']=='CONV13_BYTE_EXACT_ALTERNATING_CONFIRMED_AND_LIVE'
    tcl=r'''source E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1/firmware/camera_common.tcl
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM*#0"} -timeout 10
rc_check
mrd -bin -file E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1/final_live_before.bin 0x13800000 144
after 12000
rc_check
mrd -bin -file E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1/final_live_after.bin 0x13800000 144
disconnect
puts "CONV13_FINAL_LIVE_READONLY_COMPLETE"
exit 0
'''
    tcl=tcl.replace('E:/FPGA_Enhance_Work/road_conv13_runtime_20261028_r1',ROOT.as_posix())
    p=ROOT/'final_live.tcl';assert not (ROOT/'final_live.json').exists();p.write_text(tcl,encoding='ascii')
    run=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(p)],capture_output=True,text=True,timeout=120)
    (ROOT/'final_live.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    assert run.returncode==0 and 'CONV13_FINAL_LIVE_READONLY_COMPLETE' in run.stdout
    validate_readbacks()

def validate_readbacks():
    assert 'CONV13_FINAL_LIVE_READONLY_COMPLETE' in (ROOT/'final_live.log').read_text(encoding='utf-8')
    a,b=[struct.unpack('<144I',(ROOT/('final_live_'+x+'.bin')).read_bytes()) for x in ['before','after']]
    for m in [a,b]:
        assert m[0]==0x524f4144 and m[1]==VERSION and m[6]==m[35]==m[41]==m[74]==0
        assert m[72]==m[132]==MODE and m[80]==m[93]==2 and m[94]==m[99]==0
        assert m[17]==1483844061 and m[77]==0x5041434b and m[104]==(51 if MODE==2 else 12)
        assert m[30]==0x7084 and m[40]==0x5640
    assert b[51]-a[51]>=2 and b[39]-a[39]>=20
    write(ROOT/'final_live.json',dict(status=f'CONV13_ABI{VERSION}_MODE{MODE}_CONTINUOUS_CAMERA_CONFIRMED',selected_pl_mode=MODE,window_seconds_requested=12,detection_delta=b[51]-a[51],preview_delta=b[39]-a[39],pl_calls_last_completed_forward=b[104],all_error_status_zero=True,sd_written=False))
    print('CONV13_FINAL_LIVE_VERIFIED',b[51]-a[51],b[39]-a[39],flush=True)

if __name__=='__main__':main()
