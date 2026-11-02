"""Prepare a bounded RAM-only experiment and restore the verified FP32 hybrid."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
QAT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    arm=json.loads((ROOT/'arm_complete.json').read_text());prepared=json.loads((ROOT/'arm_prepared.json').read_text());quant=Path(prepared['quant_folder'])
    assert not arm['default_promotion_allowed'];assert sha(ROOT/'road_qconv.elf')==arm['elf_sha256'];assert sha(quant/'qmodel.bin')==prepared['model_sha256']
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=False);shutil.copy2(quant/'qmodel.bin',runtime/'qmodel.bin')
    fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures']
    for f in fixtures:
        out=runtime/'cases'/f['name'];out.mkdir(parents=True);shutil.copy2(NN/'cases'/f['name']/'input400.u32',out/'input400.u32')
    common=(OLD/'camera_common.tcl').read_text().replace('!=11','!=12').replace('19844800','5137600').replace('Unexpected FP32 all-layer','Unexpected Q8 all-layer')
    common=common.replace('26112bb4c89f99eacbd05a7fa123b2b0f906952160287bfcc3c1be9321d00d28',arm['elf_sha256']).replace('4c15d4b3ad9765f96204d0caa767e024f414149165150c94ed1701a48c4d47d1',prepared['model_sha256']).replace('e3ab5917d4b0d4bbe6b166707795603b5d6a60102ce8f68f32936a303ce58fea',arm['bit_sha256'])
    (ROOT/'camera_common.tcl').write_text(common,encoding='ascii')
    test=(OLD/'test_full_ram.tcl').read_text().replace('physical_full_r1','physical_experiment_r1').replace('road_hybrid.elf','road_qconv.elf').replace('==11','==12').replace('runtime/weights.f32','runtime/qmodel.bin').replace('ROAD_HYBRID','ROAD_QCONV').replace('{0 cpu 1 hybrid}','{0 cpu 1 fpga}').replace('${label}_timing','${label}_timing').replace('first_hybrid_full','first_fpga_full')
    live='''
 # Bounded live windows at different preview intervals; completion timestamps
 # are recorded by ARM, with no intervening JTAG polling inside each window.
 foreach period {150 100 50} {
  mwr 0x138000dc $period
  for {set k 80} {$k<88} {incr k} {mwr [expr {0x13800000+$k*4}] 0}
  mwr 0x1380000c 0
  after 300
  mwr 0x1380000c 3
  after 20000
  rc_pause
  mrd -bin -file $out/live_${period}ms_mailbox96.bin 0x13800000 96
  puts "ROAD_QCONV_LIVE_WINDOW_COMPLETE period=$period"
 }
'''
    needle=' set f [open $out/COMPLETE.txt w]';assert test.count(needle)==1;test=test.replace(needle,live+needle)
    # The compact/timing packets already contain all 80 words, including qhw telemetry.
    (ROOT/'test_ram.tcl').write_text(test,encoding='ascii')
    (ROOT/'scan_only.tcl').write_text('connect -url tcp:127.0.0.1:3121\nputs [targets]\ntargets -set -filter {name =~ "APU*"} -timeout 10\ntargets -set -filter {name =~ "ARM*#0"} -timeout 10\nputs "ROAD_QCONV_SCAN_READY"\ndisconnect\nexit\n',encoding='ascii')
    shutil.copy2(HERE/'validate_road_qconv_physical.py',ROOT/'validate_physical.py')
    # Build the real candidate renderer, not the old FP32-labelled renderer.
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');exe=ROOT/'render.exe'
    cmd=[str(gcc),'-O2','-std=c99','-Wall','-Wextra','-Werror','-I'+str(ROOT/'source'),str(ROOT/'source/road_camera_draw.c'),str(HERE/'road_camera_draw_host.c'),'-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True);(ROOT/'render_build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    checks={n:sha(ROOT/n) for n in ['road_qconv.elf','display.bit','display.xsa','ps7_init.tcl','camera_common.tcl','test_ram.tcl','scan_only.tcl','validate_physical.py','render.exe','runtime/qmodel.bin']}
    checks.update({str(p.relative_to(ROOT)):sha(p) for p in (runtime/'cases').rglob('*') if p.is_file()})
    (ROOT/'experiment_checksums.json').write_text(json.dumps(checks,indent=2));print('ROAD_QCONV_RAM_EXPERIMENT_PREPARED',flush=True)
if __name__=='__main__':main()
