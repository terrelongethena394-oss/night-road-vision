"""Prepare ARM sources and a separate Windows-compatible XSA, not old projects."""
from pathlib import Path
import json,zipfile,copy,shutil,hashlib
ROOT=Path('E:/FPGA_Enhance_Work/multinex_static_20261025')
HLS=Path('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025/multinex_project/solution_100mhz/impl/ip')
HERE=Path(__file__).resolve().parent
def main():
    shutil.copy2(HERE/'multinex_static_main.c',ROOT/'app_src/main.c')
    shutil.copy2(HLS/'drivers/multinex_hls_v1_0/src/xmultinex_hls_hw.h',ROOT/'app_src/xmultinex_hls_hw.h')
    shutil.copy2(HERE/'build_multinex_static_app.tcl',ROOT/'build_app.tcl')
    src=ROOT/'multinex_static.xsa';dest=ROOT/'multinex_static_windows.xsa'
    if not src.exists():print('ARM_SOURCES_PREPARED_WAITING_XSA');return
    assert not dest.exists(),'Preserve existing corrected XSA'
    changed=[]
    with zipfile.ZipFile(src) as a,zipfile.ZipFile(dest,'w') as b:
        for info in a.infolist():
            data=a.read(info.filename)
            if info.filename.startswith('drivers/') and info.filename.endswith('/src/Makefile'):
                new=data.replace(b'\t#echo',b'\t@echo')
                if new!=data:changed.append(info.filename)
                data=new
            b.writestr(copy.copy(info),data)
    with zipfile.ZipFile(src) as a,zipfile.ZipFile(dest) as b:
        assert b.testzip() is None
        assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==changed
        assert all('multinex' in p for p in changed),changed
        for name in ('ps7_init.tcl','ps7_init.c','ps7_init.h'):
            found=[n for n in a.namelist() if n.rsplit('/',1)[-1]==name]
            assert len(found)==1,(name,found)
            (ROOT/name).write_bytes(a.read(found[0]))
    (ROOT/'windows_xsa_fix.json').write_text(json.dumps(dict(changed=changed,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        windows_sha256=hashlib.sha256(dest.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
    print('ARM_SOURCES_AND_WINDOWS_XSA_PREPARED',changed,flush=True)
if __name__=='__main__':main()
