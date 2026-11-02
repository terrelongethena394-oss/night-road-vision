from pathlib import Path
import shutil,json,sys
BASE=Path('E:/FPGA_Enhance_Work');OUT=BASE/'camera_plate_20261026';HERE=Path(__file__).resolve().parent
def main():
    global OUT
    guarded='guarded' in sys.argv
    if guarded:OUT=BASE/'camera_plate_guarded_20261026'
    elif 'neon' in sys.argv:OUT=BASE/'camera_plate_neon_20261026'
    for n in ['test_plate_camera.tcl','validate_plate_camera.py','validate_multinex_camera.py']:shutil.copy2(HERE/n,OUT/n)
    original=(HERE/'snapshot_multinex_camera.tcl').read_text()
    old=''' set f [open $out/digit_telemetry.txt w];puts $f [mrd -value 0x03000098 15];close $f
 mrd -bin -file $out/digit_gray.bin 0x04E00000 588
 mrd -bin -file $out/digit_scores.i64 0x04E01000 66'''
    new=''' set f [open $out/plate_telemetry.txt w];puts $f [mrd -value 0x03000098 20];close $f
 mrd -bin -file $out/plate_gray.bin 0x04E00000 2304
 mrd -bin -file $out/plate_scores.i32 0x04E10000 4896
 mrd -bin -file $out/plate_tokens.bin 0x04E20000 24
 mrd -bin -file $out/plate_normalized.i16 0x04E30000 4608'''
    assert old in original;(OUT/'snapshot_plate_camera.tcl').write_text(original.replace(old,new),encoding='ascii')
    if guarded:
        for name in ['test_plate_camera.tcl','snapshot_plate_camera.tcl']:
            p=OUT/name;t=p.read_text()
            t=t.replace('lindex $words 1]+0}]!=7','lindex $words 1]+0}]!=8').replace('mrd -value 0x03000098 20','mrd -value 0x03000098 22')
            t=t.replace('plate_gray.bin 0x04E00000 2304','plate_gray.bin 0x04E00000 3072').replace('plate_scores.i32 0x04E10000 4896','plate_scores.i32 0x04E10000 6528').replace('plate_tokens.bin 0x04E20000 24','plate_tokens.bin 0x04E20000 32').replace('plate_normalized.i16 0x04E30000 4608','plate_normalized.i16 0x04E30000 6144')
            p.write_text(t,encoding='ascii')
    offline=json.loads((OUT/'offline_camera.json').read_text());offline['performance_acceptance_hz']=4.0
    (OUT/'offline_camera.json').write_text(json.dumps(offline,indent=2),encoding='utf-8')
    print('PLATE_RUNTIME_TOOLS_READY',flush=True)
if __name__=='__main__':main()
