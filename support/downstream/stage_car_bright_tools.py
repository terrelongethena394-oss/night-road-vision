import shutil,py_compile
from pathlib import Path
from shadowlift_lab import BASE,ROOT as LAB,read,write,sha
HERE=Path(__file__).resolve().parent;OLDROOT=BASE/'road_car_pair_20261030_r1';ROOT=BASE/'road_car_bright_20261030_r1';APP=ROOT/'firmware'
def main():
 tools=ROOT/'tools';tools.mkdir()
 for name in ['_capture_io.py','car_pair_common.py','car_pair_tools.py','car_pair_entry.py']:
  s=(OLDROOT/'tools'/name).read_text(encoding='utf-8');s=s.replace('road_car_pair_20261030_r1','road_car_bright_20261030_r1')
  if name=='car_pair_tools.py':
   s=s.replace('m[1]==26','m[1]==27');old="cp=read(BASE/'road_retinex_noiseguard_arm_20261029_r1/c_complete.json');lib=ct.CDLL(str(Path(cp['attempt'])/'retinex.dll'))";assert old in s;s=s.replace(old,"lib=ct.CDLL(str(APP/'host/shadow.dll'))")
  if name=='car_pair_entry.py':s=s.replace('ABI26_CAR_PAIR_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED','ABI27_CAR_BRIGHT_DISPLAY_BOARD_VERIFIED')
  (tools/name).write_text(s,encoding='utf-8')
 for name in ['car_bright_mode.py','verify_car_bright_board.py']:shutil.copy2(HERE/name,tools/name)
 for p in tools.glob('*.py'):py_compile.compile(str(p),doraise=True)
 (ROOT/'使用说明.md').write_text('''# 提亮增强版

默认左原图、右增强图。两侧相同的汽车框均来自原图检测，用于单独观察画质变化；不代表增强导致检测提升。

02_models.cmd切换到两模型对照页（左稳定、右新版，背景均为增强图）。03_enhancement.cmd返回原图/增强图页；切页不需要重跑神经网络。

01_capture_camera.cmd拍摄一个新的摄像头快照，两套模型计算结束后更新。04_fixed_road.cmd返回固定道路图。00_restore_ABI26.cmd恢复原对照版。

当前已编译并通过37组C/NumPy检查，尚未上板。完整验收通过后才生成board_verified.json。SD卡/Flash不改，原ABI26保留。
''',encoding='utf-8')
 configs=[('01_capture_camera.cmd','car_pair_entry.py','capture'),('02_models.cmd','car_bright_mode.py','1'),('03_enhancement.cmd','car_bright_mode.py','0'),('04_fixed_road.cmd','car_pair_entry.py','photo'),('05_start_camera.cmd','car_pair_entry.py','start'),('06_full_acceptance.cmd','verify_car_bright_board.py','')]
 for name,script,arg in configs:(ROOT/name).write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "'+str(tools/script)+'" '+arg+'\r\npause\r\n',encoding='ascii')
 (ROOT/'00_restore_ABI26.cmd').write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "E:\\FPGA_Enhance_Work\\road_car_pair_20261030_r1\\tools\\car_pair_entry.py" start\r\npause\r\n',encoding='ascii')
 fixture=read(ROOT/'fixtures/road/fixture.json');fixture.update(previous_enhancement_sha256=fixture['enhancement_sha256'],enhancement_sha256=sha(ROOT/'fixtures/road/enhanced.u32'),same_enhanced_background_both_sides=False,default_UI='RAW vs ENHANCED with same candidate car boxes',enhancement_mean_target=62);write(ROOT/'fixtures/road/fixture.json',fixture)
 write(APP/'runtime_checksums.json',{str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']});write(ROOT/'offline_ready.json',dict(status='ABI27_SHADOW_DISPLAY_OFFLINE_READY_NOT_BOARD_TESTED',elf_sha256=sha(APP/'road_detail.elf'),source_C_proof_sha256=sha(LAB/'c_complete.json'),weights_unchanged=True,bit_unchanged=True,sd_written=False));print('CAR_BRIGHT_TOOLS_STAGED',flush=True)
if __name__=='__main__':main()
