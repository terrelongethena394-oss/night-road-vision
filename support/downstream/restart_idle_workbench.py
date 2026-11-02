"""Stop only our idle GUI process when replacing a broken UI callback."""
import argparse,ctypes,subprocess
from photo_station_core import DELIVERY,STAGING
assert not (STAGING/'jtag.lock').exists(),'A hardware task is active; do not stop the GUI.'
p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);a=p.parse_args()
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p
k.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
k.CloseHandle.argtypes=[ctypes.c_void_p]
handle=k.OpenProcess(0x1000,False,a.pid);assert handle,'Our recorded launcher PID no longer exists'
try:
    name=ctypes.create_unicode_buffer(32768);n=ctypes.c_uint32(len(name))
    assert k.QueryFullProcessImageNameW(handle,0,name,ctypes.byref(n))
    assert name.value.replace('\\','/').casefold()=='e:/fpga_enhance_work/nn_env312/scripts/pythonw.exe'
finally:k.CloseHandle(handle)
subprocess.run(['taskkill','/PID',str(a.pid),'/T','/F'],check=True)
print('IDLE_RECORDED_WORKBENCH_STOPPED',a.pid,flush=True)
