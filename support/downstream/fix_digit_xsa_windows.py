"""Change only TAB #echo recipes in generated HLS driver Makefiles for CMD."""
from pathlib import Path
import copy
import hashlib
import json
import zipfile
ROOT=Path('E:/FPGA_Enhance_Work/camera_nn_digit_20261023')
src=ROOT/'camera_digit.xsa';dest=ROOT/'camera_digit_windows.xsa'
assert src.exists() and not dest.exists()
changed=[]
with zipfile.ZipFile(src) as a,zipfile.ZipFile(dest,'w') as b:
    for info in a.infolist():
        data=a.read(info.filename)
        if info.filename.endswith('/src/Makefile') and info.filename.startswith('drivers/'):
            new=data.replace(b'\t#echo',b'\t@echo')
            if new!=data:changed.append(info.filename)
            data=new
        b.writestr(copy.copy(info),data)
with zipfile.ZipFile(src) as a,zipfile.ZipFile(dest) as b:
    assert b.testzip() is None
    assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==changed
assert len(changed)==2 and any('digit_monitor' in x for x in changed) and any('nanodce8_full' in x for x in changed)
(ROOT/'windows_driver_fix.json').write_text(json.dumps(dict(status='PASS',changed=changed,
    original_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),windows_sha256=hashlib.sha256(dest.read_bytes()).hexdigest()),indent=2))
print('DIGIT_WINDOWS_DRIVER_FIX_PASS')
