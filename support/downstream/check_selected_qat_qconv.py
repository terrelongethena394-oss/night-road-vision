"""Model-specific C simulation using actual QAT parameters and cropped real inputs."""
from pathlib import Path
import csv,hashlib,importlib.util,json,subprocess
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_qatcases_20261027')
QAT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
def main():
    selected=json.loads((QAT/'selection_complete.json').read_text());folder=QAT/'exports'/f'epoch{selected["selected_epoch"]}';assert (folder/'host_complete.json').exists()
    p=HERE/'prepare_road_qconv.py';s=importlib.util.spec_from_file_location('qat_fixture_preparer',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.ROOT=ROOT;m.OLD=folder;m.TRACE_ROOT=folder/'host/02e67bab-27594c1d/trace';m.CROP_REAL=True;m.main()
    with (ROOT/'csim.log').open('w') as f:subprocess.run(['E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat','-f',str(ROOT/'csim.tcl')],stdout=f,stderr=subprocess.STDOUT)
    assert 'ROAD_QCONV_CSIM_COMPLETE' in (ROOT/'csim.log').read_text(errors='replace')
    rows=list(csv.DictReader((ROOT/'tb_all.csv').open()));assert len(rows)==66 and all(int(r['byte_differences'])==0 for r in rows)
    # The synthesized source must remain the same model-independent hardware.
    base=Path('E:/FPGA_Enhance_Work/road_qconv_hls_20261027')
    for name in ['road_qconv_hls.cpp','road_qconv_hls.h']:assert (ROOT/name).read_bytes()==(base/name).read_bytes()
    receipt=dict(status='QAT_PARAMETERS_ALL60_CROPPED_REAL_CONVS_PLUS6_BOUNDARIES_BYTES_EXACT_IN_HLS_CSIM',full_resolution=False,rows=rows,quant_model_sha256=hashlib.sha256((folder/'qmodel.bin').read_bytes()).hexdigest(),hardware_access=False,sd_written=False,default_promotion_allowed=False)
    (ROOT/'checked.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print('SELECTED_QAT_HLS_MODEL_SPECIFIC_CSIM_PASS',flush=True)
if __name__=='__main__':main()
