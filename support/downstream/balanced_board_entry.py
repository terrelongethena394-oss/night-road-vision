"""Explicit user controls, always RAM-only; reader checks every new capture."""
import sys,time
from pathlib import Path
from balanced_board_tools import ROOT,APP,start,capture,restore_previous,run
from car_box_refine_common import read,write

def main():
 mode=sys.argv[1] if len(sys.argv)>1 else 'verify'
 if mode=='verify':
  from verify_balanced_board import main as verify
  verify();return
 out=ROOT/('manual_20261030_'+time.strftime('%H%M%S'));out.mkdir()
 if mode=='restore27':print(restore_previous(out));return
 if mode in ['start_camera','start_photo']:start(out)
 if mode in ['start_camera','capture']:capture(out/'packet',4,view=1)
 elif mode in ['start_photo','photo']:capture(out/'packet',5,ROOT/'fixtures/road0.bgr',view=1)
 elif mode in ['raw_enh','models']:
  view=0 if mode=='raw_enh' else 1
  p=out/'mode.tcl';p.write_text(f'''source {APP.as_posix()}/camera_common.tcl
connect -url tcp:127.0.0.1:3121
if {{[catch {{
 targets -set -filter {{name =~ "ARM*#0"}} -timeout 10
 loadhw -hw $root/display.xsa
 rc_check
 if {{[word 0x13800008]==3 && [word 0x13800270]!=1}} {{error "Cannot change view during incomplete inference"}}
 mwr 0x1380000c 0
 after 300
 mwr 0x138002bc {view}
 mwr 0x1380000c 6
 after 300
 rc_check
 disconnect
 puts "BALANCED_VIEW_CHANGED"
}} why]}} {{puts stderr $why;catch {{disconnect}};exit 1}}
exit 0
''',encoding='ascii');run(p,out/'mode.log','BALANCED_VIEW_CHANGED');print('BALANCED_DISPLAY_PAGE',view,flush=True)
 elif mode not in ['start_camera','start_photo','capture','photo']:raise ValueError('Unknown entry mode')

if __name__=='__main__':main()
