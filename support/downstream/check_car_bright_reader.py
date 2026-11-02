"""Adapt the existing offline reader corruption tests to ABI27's new display."""
from pathlib import Path
import subprocess
from shadowlift_lab import BASE,read,write,sha
ROOT=BASE/'road_car_bright_20261030_r1'
def main():
 s=Path(__file__).with_name('check_car_pair_reader.py').read_text();s=s.replace('from road_accuracy_common import sensor400\n','').replace('1:26,','1:27,');p=ROOT/'tools/check_offline_reader.py';p.write_text(s,encoding='utf-8')
 result=subprocess.run(['E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe',str(p)],capture_output=True,text=True);(ROOT/'reader_check.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0,result.stdout+result.stderr
 assert read(ROOT/'reader_complete.json')['not_board_verification'];print('CAR_BRIGHT_READER_VALID_AND_CORRUPTION_TESTS_PASS',flush=True)
if __name__=='__main__':main()
