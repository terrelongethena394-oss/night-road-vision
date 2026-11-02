import ctypes as c,json,time
from pathlib import Path
class Memory(c.Structure):
    _fields_=[('length',c.c_ulong),('load',c.c_ulong)]+[(n,c.c_ulonglong) for n in ['total','available','total_page','available_page','total_virtual','available_virtual','extended']]
m=Memory();m.length=c.sizeof(m);assert c.windll.kernel32.GlobalMemoryStatusEx(c.byref(m))
p=Path('E:/FPGA_Enhance_Work/road_allview_gammafit_20261031_r1/history.json')
h=json.loads(p.read_text()) if p.exists() else []
print(json.dumps(dict(RAM_total_GB=m.total/2**30,RAM_available_GB=m.available/2**30,history=h[-2:]),ensure_ascii=False))
