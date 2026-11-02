"""Show and validate enhancement view after the six physical engineering cases."""
from datetime import datetime
from roi_delivery_board_tools import BOARD, capture, restore
from car_roi_delivery_common import read, write

def main():
    assert read(BOARD/'board_verified.json')['physical_readback']
    out=BOARD/datetime.now().strftime('enhancement_display_%Y%m%d_%H%M%S')
    out.mkdir()
    try:
        result=capture(out/'capture',kind=5,source=BOARD/'fixtures/road0.bgr',photo=1,view=0)
        write(BOARD/'final_display.json',dict(status='ACTUAL_ENHANCEMENT_VIEW_VERIFIED',capture=str(out/'capture'),result=result,sd_written=False))
        print('ROI_FINAL_ENHANCEMENT_DISPLAY_VERIFIED',out,flush=True)
    except Exception as error:
        failure=dict(error=str(error),sd_written=False)
        try:failure['restoration']=restore(out)
        except Exception as restore_error:failure['restoration']=dict(status='FAILED',error=str(restore_error))
        write(out/'display_failed.json',failure)
        raise

if __name__=='__main__':main()
