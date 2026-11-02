"""Leave sequential pipeline evaluator running; terminate only our duplicate stream."""
import ctypes as c,os,signal
from pathlib import Path
def processes():
    from ctypes import wintypes as w
    k=c.WinDLL('kernel32',use_last_error=True);nt=c.WinDLL('ntdll')
    class Entry(c.Structure):
        _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',c.c_size_t),('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('exe',w.WCHAR*260)]
    class Unicode(c.Structure):_fields_=[('length',w.USHORT),('maximum',w.USHORT),('buffer',c.c_void_p)]
    k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE;k.Process32FirstW.argtypes=k.Process32NextW.argtypes=[w.HANDLE,c.POINTER(Entry)];k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE;k.CloseHandle.argtypes=[w.HANDLE]
    nt.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)];nt.NtQueryInformationProcess.restype=w.LONG
    snap=k.CreateToolhelp32Snapshot(2,0);assert snap and snap!=c.c_void_p(-1).value;e=Entry();e.size=c.sizeof(e);ok=k.Process32FirstW(snap,c.byref(e));rows=[]
    while ok:
        if e.exe.lower()=='python.exe':
            handle=k.OpenProcess(0x1000,False,e.pid)
            if handle:
                needed=w.ULONG();nt.NtQueryInformationProcess(handle,60,None,0,c.byref(needed))
                if 0<needed.value<1048576:
                    buf=c.create_string_buffer(needed.value)
                    if nt.NtQueryInformationProcess(handle,60,buf,len(buf),c.byref(needed))==0:
                        text=c.cast(buf,c.POINTER(Unicode)).contents;start=c.addressof(buf)
                        if start<=text.buffer<=start+len(buf)-text.length:rows.append(dict(ProcessId=e.pid,CommandLine=c.wstring_at(text.buffer,text.length//2)))
                k.CloseHandle(handle)
        ok=k.Process32NextW(snap,c.byref(e))
    k.CloseHandle(snap);return rows
def main():
    rows=processes();matches=[r for r in rows if 'evaluate_allview_gamma_20261031.py' in (r.get('CommandLine') or '')]
    streamed=[r for r in matches if '--stream' in r['CommandLine']];normal=[r for r in matches if '--stream' not in r['CommandLine']]
    assert 1<=len(streamed)<=2 and 1<=len(normal)<=2,[(r['ProcessId'],r['CommandLine']) for r in matches]
    for r in sorted(streamed,key=lambda r:'nn_env312' in r['CommandLine']):
        try:os.kill(int(r['ProcessId']),signal.SIGTERM)
        except ProcessLookupError:pass
    flag=Path('E:/FPGA_Enhance_Work/road_allview_gammafit_20261031_r1/streaming_evaluation_active.flag');assert flag.resolve().parent==Path('E:/FPGA_Enhance_Work/road_allview_gammafit_20261031_r1').resolve();flag.unlink()
    print('DUPLICATE_STREAM_STOPPED',[r['ProcessId'] for r in streamed],'PIPELINE_EVALUATOR_CONTINUES',[r['ProcessId'] for r in normal])
if __name__=='__main__':main()
