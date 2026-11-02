from pathlib import Path
import json,time,sys
import torch
from tiny_plate_integer import IntegerPlate
from validate_plate_camera import validate
ROOT=Path('E:/FPGA_Enhance_Work/camera_plate_neon_20261026')
def main():
    global ROOT
    if len(sys.argv)>1:ROOT=Path(sys.argv[1])
    cases=json.loads((ROOT/'plate_cases.json').read_text(encoding='utf-8'));done=set();start=time.monotonic();torch.set_num_threads(4)
    q=IntegerPlate(torch.load(ROOT/'plate_model.pth',weights_only=True,map_location='cpu'))
    while len(done)<len(cases):
        if time.monotonic()-start>600:raise TimeoutError('Plate captures incomplete')
        progress=False
        for c in cases:
            folder=ROOT/'board_plate'/c['id']
            if c['id'] in done or not (folder/'resumed.txt').exists():continue
            result=validate(folder,ROOT,q);done.add(c['id']);progress=True
            print('PLATE_BOARD_CASE_VERIFIED',len(done),len(cases),c['id'],json.dumps(result['displayed'],ensure_ascii=True),flush=True)
        if not progress:time.sleep(1)
    (ROOT/'batch_validation_complete.json').write_text(json.dumps(dict(status='ALL_PLATE_BOARD_CASES_VALIDATED',n=len(done),seconds=time.monotonic()-start),indent=2),encoding='utf-8')
    print('ALL_PLATE_BOARD_CASES_VERIFIED',len(done),flush=True)
if __name__=='__main__':main()
