"""Audit compatible board wiring and stage a volatile fixed-image runtime."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,zipfile,xml.etree.ElementTree as ET
from train_real_digit_cnn import OUT

BUILD=Path('E:/FPGA_Enhance_Work/camera_real_cnn_score64_20261025')
TEST=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_score64_20261025')
OLD=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')
HERE=Path(__file__).resolve().parent

def main():
    log=(BUILD/'build_board.log').read_text(encoding='utf-8',errors='replace')
    m=re.search(r'REAL_CNN_BOARD_BUILD_PASS WNS=([-.0-9]+) WHS=([-.0-9]+)',log);assert m
    wns,whs=map(float,m.groups());assert min(wns,whs)>=0
    verify=(OUT/'hls_score64/verify.log').read_text(encoding='utf-8',errors='replace')
    stream=(OUT/'rtl_stream_score64/simulate.log').read_text(encoding='utf-8',errors='replace')
    assert 'REAL_CNN_CORRECTED_FULL_VERIFY_PASS' in verify and 'C/RTL co-simulation finished: PASS' in verify
    assert 'REAL_CNN_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS' in stream
    audit=(HERE/'audit_digit_board.py').read_text(encoding='utf-8').replace('E:/FPGA_Enhance_Work/camera_nn_digit_20261023',BUILD.as_posix())
    audit=audit.replace('E:/FPGA_Enhance_Work/digit_recognition_20261023/hls/digit_weights.h',(OUT/'hls_score64/cnn_weights.h').as_posix())
    (BUILD/'audit_integration.py').write_text(audit,encoding='utf-8')
    subprocess.run([sys.executable,str(BUILD/'audit_integration.py')],check=True)
    board=TEST/'board';board.mkdir(exist_ok=True)
    shutil.copy2(BUILD/'system_wrapper.bit',board/'system_wrapper.bit')
    shutil.copy2(BUILD/'camera_digit.xsa',board/'camera_digit.xsa')
    with zipfile.ZipFile(board/'camera_digit.xsa') as z:
        assert z.testzip() is None
        entries=[n for n in z.namelist() if n.endswith('ps7_init.tcl')];assert len(entries)==1
        ps=z.read(entries[0]);assert ps==(OLD/'board/ps7_init.tcl').read_bytes(),'PS initialization changed'
        (board/'ps7_init.tcl').write_bytes(ps)
    oldxdc=Path('E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd/ov5640_lcd.srcs/constrs_1/new/pin.xdc')
    newxdc=BUILD/'prj/camera_digit.srcs/constrs_1/imports/new/pin.xdc'
    if not newxdc.exists():
        entries=[e.attrib['Path'] for e in ET.parse(BUILD/'prj/camera_digit.xpr').iter('File') if e.attrib.get('Path','').endswith('/pin.xdc')]
        assert len(entries)==1
        newxdc=Path(entries[0].replace('$PPRDIR',(BUILD/'prj').as_posix())).resolve()
        assert newxdc==oldxdc.resolve()
    assert oldxdc.read_bytes()==newxdc.read_bytes()
    status=dict(status='ROUTED_TIMING_PASSED_READY_FOR_JTAG_VALIDATION',wns=wns,whs=whs,
        model_sha256=hashlib.sha256((OUT/'real_digit_cnn.pth').read_bytes()).hexdigest(),
        bit_sha256=hashlib.sha256((board/'system_wrapper.bit').read_bytes()).hexdigest(),
        elf_sha256=hashlib.sha256((TEST/'image_test.elf').read_bytes()).hexdigest(),
        ps7_init_sha256=hashlib.sha256(ps).hexdigest(),
        ps7_init_unchanged=True,pin_constraints_unchanged=True,
        numerical_evidence='C/RTL6frames1586329pixels; native AXI/reset/backpressure5frames123339pixels',
        sd_written=False,hardware_downloaded=False)
    (TEST/'runtime_identity.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print('REAL_CNN_RUNTIME_STAGED',json.dumps(status),flush=True)

if __name__=='__main__':main()
