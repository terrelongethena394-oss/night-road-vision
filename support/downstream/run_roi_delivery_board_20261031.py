"""Manual RAM-only entry point for the frozen ABI30 engineering experiment."""
import argparse
from datetime import datetime
from roi_delivery_board_tools import BOARD, start, capture, restore
from car_roi_delivery_common import read, write

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=['road0','road1','camera'],default='road0')
    p.add_argument('--view',choices=['enhancement','comparison'],default='enhancement')
    p.add_argument('--start',action='store_true',help='Reset and load ABI30 into RAM before capture')
    p.add_argument('--restore',action='store_true',help='Restore ABI29 camera idle preview into RAM')
    a=p.parse_args()
    out=BOARD/datetime.now().strftime('manual_%Y%m%d_%H%M%S')
    out.mkdir()
    try:
        if a.restore:
            result=restore(out)
        else:
            assert read(BOARD/'board_verified.json')['physical_readback']
            if a.start:
                start(out)
            source=None if a.case=='camera' else BOARD/'fixtures'/f'{a.case}.bgr'
            result=capture(out/'capture',kind=4 if a.case=='camera' else 5,
                           source=source,photo=1 if a.case!='road1' else 2,
                           view=int(a.view=='comparison'))
        write(out/'manual_result.json',result)
        print('ROI_MANUAL_RAM_OPERATION_DONE',out,flush=True)
    except Exception as error:
        failure={'error':str(error),'sd_written':False,'restore_attempted':True}
        try:
            failure['restoration']=restore(out)
        except Exception as restore_error:
            failure['restoration']={'status':'FAILED','error':str(restore_error)}
        write(out/'manual_failed.json',failure)
        raise

if __name__=='__main__':
    main()
