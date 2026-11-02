"""User entry: same-image enhancement/display and actual FPGA-assisted detection."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys,struct
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
APP=Path(MANIFEST['verified_firmware'])
PYTHON='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe'
XSCT='E:/Xilinx/Vitis/2020.2/bin/xsct.bat'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def verify_files():
    for name,digest in MANIFEST['firmware_sha256'].items():
        assert sha(APP/name)==digest,name
    for name,digest in MANIFEST['entry_sha256'].items():
        assert sha(ROOT/name)==digest,name

def show(photo,detail):
    assert 1<=photo<=len(MANIFEST['photos']) and detail in (0,1)
    f=MANIFEST['photos'][photo-1];case=APP/'runtime/cases'/f['id']
    for name,digest in f['sha256'].items():assert sha(case/name)==digest
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    evidence=ROOT/'board_evidence';evidence.mkdir(exist_ok=True)
    out=evidence/f'{stamp}_photo{photo}_detail{detail}'
    command=[XSCT,str(ROOT/'static_quality_demo.tcl'),str(APP),f['id'],str(detail),str(photo),str(f['input_fnv32']),str(f['roi_fnv32']),str(out)]
    print(f'Computing fixed road photo {photo}, detail={detail}; SD/Flash unchanged.',flush=True)
    p=subprocess.run(command,capture_output=True,text=True,timeout=240)
    log=p.stdout+p.stderr;(evidence/(out.name+'.log')).write_text(log,encoding='utf-8');print(log,flush=True)
    assert p.returncode==0 and 'STATIC_QUALITY_DEMO_COMPLETE' in p.stdout,'Board command failed; do not infer success from XSCT exit code'
    m=struct.unpack('<144I',(out/'mail.bin').read_bytes())
    assert m[0]==0x524f4144 and m[1]==18 and m[2]==3 and m[57]==1 and m[56]==1
    assert m[6]==m[35]==m[41]==m[74]==0 and m[72]==m[132]==2 and m[93]==2
    assert m[99]==detail and m[104]==(102 if detail else 51)
    assert (out/'raw.u32').read_bytes()==(case/'input400.u32').read_bytes()
    expected=ROOT/'reference'/f'{photo:02}_enhanced.u32'
    assert (out/'enhanced.u32').read_bytes()==expected.read_bytes()
    gold=case/('gold_detail_boxes400.f32' if detail else 'gold_raw_boxes400.f32')
    assert (out/'boxes.f32').read_bytes()==gold.read_bytes()
    render=subprocess.run([str(APP/'host/render.exe'),str(out/'raw.u32'),str(out/'enhanced.u32'),str(out/'boxes.f32'),str(out/'ui.u32'),str(out/'expected.bgr')],capture_output=True,text=True,timeout=30)
    (out/'render.log').write_text(render.stdout+render.stderr,encoding='utf-8')
    assert render.returncode==0 and 'GUARDS_PASS' in render.stdout
    assert (out/'expected.bgr').read_bytes()==(out/'frame.bgr').read_bytes()
    Image.fromarray(np.fromfile(out/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'lcd_readback.png')
    boxes=np.fromfile(out/'boxes.f32','<f4').reshape(-1,6)
    counts={name:int((boxes[:,5]==i).sum()) for i,name in enumerate(['person','car','truck','bus'])}
    result=dict(status='STATIC_SAME_IMAGE_ENHANCEMENT_DETECTION_FRAME_VERIFIED',photo=photo,fixture=f['id'],detail_mode=detail,source_timeofday=f['timeofday'],counts=counts,processing_seconds=(m[19]+(m[20]<<32))/m[18],pl_calls=m[104],image_source='Fixed public road photograph injected through JTAG; no camera pixels used as inference input',enhancement_role='Adaptive Gamma display; detector uses raw image',sd_written=False,framebuffer_sha256=sha(out/'frame.bgr'),evidence=str(out))
    write(out/'verified.json',result);write(ROOT/'last_board_result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result

def main():
    verify_files()
    args=sys.argv[1:]
    if args==['start']:
        subprocess.run([PYTHON,str(APP/'user_start.py')],check=True,timeout=520)
        show(1,MANIFEST['default_detail_mode'])
    elif args and args[0]=='show' and len(args) in (2,3):
        show(int(args[1]),int(args[2]) if len(args)==3 else MANIFEST['default_detail_mode'])
    elif args and args[0]=='compare' and len(args)==2:
        single=show(int(args[1]),0);detail=show(int(args[1]),1)
        write(ROOT/'last_comparison.json',dict(single=single,detail=detail,warning='Box counts are predictions, not detection accuracy.'))
    else:raise SystemExit('Use: start | show PHOTO [DETAIL0or1] | compare PHOTO')

if __name__=='__main__':main()
