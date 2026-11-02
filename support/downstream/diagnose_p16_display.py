"""Preserve visual failure separately; inspect current RAM without reset/download."""
from pathlib import Path
import json, subprocess, struct, datetime

ROOT=Path('E:/FPGA_Enhance_Work/road_conv13_p16_runtime_20261028_r1')
APP=ROOT/'firmware'

def main():
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out=ROOT/('display_diagnostic_'+stamp)
    out.mkdir()
    feedback=dict(status='MANUAL_DISPLAY_FAILURE_UNRESOLVED',user_feedback='画面异常或停止更新',stable_promotion_allowed=False,sd_written=False)
    (ROOT/'manual_display_status.json').write_text(json.dumps(feedback,ensure_ascii=False,indent=2),encoding='utf-8')
    tcl=f'''connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
puts "CPU_STATE [state]"
mrd -bin -file {out.as_posix()}/mail_before.bin 0x13800000 144
mrd -bin -file {out.as_posix()}/vdma_before.bin 0x43000000 48
after 12000
mrd -bin -file {out.as_posix()}/mail_after.bin 0x13800000 144
mrd -bin -file {out.as_posix()}/vdma_after.bin 0x43000000 48
disconnect
puts "DISPLAY_READONLY_DIAGNOSTIC_COMPLETE"
exit 0
'''
    p=out/'inspect.tcl';p.write_text(tcl,encoding='ascii')
    run=subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/xsct.bat',str(p)],capture_output=True,text=True,timeout=100)
    (out/'inspect.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    print(run.stdout+run.stderr,flush=True)
    assert 'DISPLAY_READONLY_DIAGNOSTIC_COMPLETE' in run.stdout
    names={0:'magic',1:'abi',2:'state',3:'command',5:'heart',6:'error',30:'lcd',32:'frame',35:'dma_read',38:'lcd_state',39:'preview',40:'camera',41:'dma_write',51:'detections',56:'test',57:'pause_ack',61:'capture_slot',72:'pl_mode',73:'calls',74:'pl_error',80:'pipeline',94:'detail',104:'completed_calls',132:'started_mode'}
    a,b=[struct.unpack('<144I',(out/f'mail_{s}.bin').read_bytes()) for s in ['before','after']]
    result={'before':{n:a[i] for i,n in names.items()},'after':{n:b[i] for i,n in names.items()},'preview_delta':(b[39]-a[39])&0xffffffff,'detection_delta':(b[51]-a[51])&0xffffffff,'sd_written':False}
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));print('DIAGNOSTIC_DIR',out,flush=True)

if __name__=='__main__':main()
