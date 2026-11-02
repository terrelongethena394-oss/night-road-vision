"""Start the installed GUI with a diagnostic log, without a console window."""
import subprocess
from photo_station_core import DELIVERY,STAGING
from car_roi_delivery_common import write
with (STAGING/'camera_gui.log').open('w',encoding='utf-8') as log:
    p=subprocess.Popen(['E:/FPGA_Enhance_Work/nn_env312/Scripts/pythonw.exe',str(DELIVERY/'程序/photo_station_gui.py')],
        cwd=str(DELIVERY),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=0x00000008|0x00000200)
write(STAGING/'camera_gui_process.json',dict(pid=p.pid))
print('CAMERA_WORKBENCH_STARTED',p.pid,flush=True)
