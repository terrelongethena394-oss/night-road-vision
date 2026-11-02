"""Start verified camera firmware or trigger exactly one new frozen capture."""
import datetime,sys
from camera_snapshot_tools import *
def main():
 assert len(sys.argv)==2 and sys.argv[1] in ['start','capture']
 proof=read(ROOT/'board_verified.json');assert proof['status']=='ABI24_CAMERA_ONESHOT_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED'
 assert proof['elf_sha256']==sha(APP/'road_detail.elf') and proof['bit_sha256']==sha(APP/'display.bit')
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items())
 out=ROOT/'user_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
 print('ONE_SHOT_CAMERA: hold scene steady; four detections use one frozen frame.',flush=True)
 if sys.argv[1]=='start':start(out)
 # Neural equivalence has already been tested. Routine capture does not run
 # the detector again on the PC; board predictions are verified/read back.
 result=capture(out/'shot',4,check_native=False)
 print('CAMERA_SHOT_READY',result['capture_id'],'board_seconds',round(result['processing_seconds'],3),'boxes',result['new_boxes'],flush=True)
if __name__=='__main__':main()
