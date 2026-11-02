"""Reuse the unchanged independent C/CUDA verification contract for selected QAT."""
from pathlib import Path
import importlib.util,json,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
HERE=Path(__file__).resolve().parent
def main():
    selection=json.loads((ROOT/'selection_complete.json').read_text());epoch=selection['selected_epoch'];assert epoch is not None
    path=HERE/'verify_road_integer_host.py';s=importlib.util.spec_from_file_location('qat_c_verifier',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.ROOT=ROOT/'exports';sys.argv=[str(path),f'epoch{epoch}'];m.main()
    print('SELECTED_QAT_EXACT_C_ALL8_ALL86_VERIFIED_NO_BOARD_ACCESS',flush=True)
if __name__=='__main__':main()
