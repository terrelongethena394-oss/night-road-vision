import datetime,sys
from car_pair_tools import *
def main():
 assert len(sys.argv)==2 and sys.argv[1] in ['start','capture','photo']
 proof=read(ROOT/'board_verified.json');assert proof['status']=='ABI26_CAR_PAIR_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED' and proof['elf_sha256']==sha(APP/'road_detail.elf')
 assert all(sha(APP/n)==h for n,h in read(APP/'runtime_checksums.json').items());out=ROOT/'user_runs'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True)
 if sys.argv[1]=='start':start(out)
 r=capture(out/'shot',5,ROOT/'fixtures/road/source800.bgr',1,check_native=False) if sys.argv[1]=='photo' else capture(out/'shot',4,check_native=False)
 print('CAR_PAIR_SHOT_READY',r,flush=True)
if __name__=='__main__':main()
