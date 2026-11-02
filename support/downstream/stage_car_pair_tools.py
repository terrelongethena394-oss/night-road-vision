import shutil,py_compile,sys
from car_pair_common import *
HERE=Path(__file__).resolve().parent
def main():
 assert read(ROOT/'post_complete.json')['images']==1472
 refresh='--refresh' in sys.argv;assert not refresh or ((ROOT/'offline_ready.json').exists() and not (ROOT/'board_verified.json').exists())
 tools=ROOT/'tools';tools.mkdir(exist_ok=refresh);s=(HERE/'camera_snapshot_tools.py').read_text();s=s[:s.index('\ndef validate(')]
 old="ROOT=Path('E:/FPGA_Enhance_Work/road_camera_snapshot_20261030_r1')";assert old in s;s=s.replace(old,"ROOT=Path('"+ROOT.as_posix()+"')");s=s.replace('mail.bin 0x13800000 160','mail.bin 0x13800000 176')
 marker=' set n [word 0x138000d0]';assert s.count(marker)==1
 s=s.replace(marker,''' for {{set j 0}} {{$j<4}} {{incr j}} {{
  mrd -bin -file {d}/stable_decoded$j.f32 [expr {{0x1B800000+$j*0x40000}}] 56700
 }}
'''+marker)
 (tools/'_capture_io.py').write_text(s,encoding='utf-8')
 for n in ['car_pair_common.py','car_pair_tools.py','verify_car_pair_board.py','car_pair_entry.py']:shutil.copy2(HERE/n,tools/n)
 for p in tools.glob('*.py'):py_compile.compile(str(p),doraise=True)
 for name,script,arg in [('01_start_car_comparison.cmd','car_pair_entry.py','start'),('02_capture_again.cmd','car_pair_entry.py','capture'),('03_full_acceptance.cmd','verify_car_pair_board.py',''),('04_fixed_road_photo.cmd','car_pair_entry.py','photo')]:
  (ROOT/name).write_text('@echo off\r\ncd /d '+ROOT.as_posix().replace('/','\\')+'\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "'+str(tools/script)+'" '+arg+'\r\npause\r\n',encoding='ascii')
 (ROOT/'00_restore_stable_ABI24.cmd').write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "E:\\FPGA_Enhance_Work\\road_camera_snapshot_20261030_r1\\tools\\camera_snapshot_entry.py" start\r\npause\r\n',encoding='ascii')
 (ROOT/'使用说明.md').write_text('''# 汽车专项对照版

左边稳定模型，右边第4轮微调模型。两模型读取同一个冻结画面的相同四个未增强视图，只显示car类别；神经网络结构仍有四类输出，其他类别在显示前过滤。

两边背景使用同一张Retinex增强图，使汽车框对比不受背景亮度差异干扰。这个界面没有证明增强提高识别；本轮增强算法未改。每次拍摄执行8次网络前向、408次PL调用，属于单帧对照，耗时需要上板测量。

目前编译及离线后处理通过。只有生成board_verified.json后，01/02快捷入口才允许使用；03执行完整验收，失败时尝试恢复ABI24稳定摄像头版本。SD卡和Flash不修改。

汽车AP50独立图片证据见scope.json。此前四类综合验收未通过的记录保留，不能称为四类模型全面提升。没有标注的实物摄像头画面只检查功能和数值，不作为准确率证据。
''',encoding='utf-8')
 write(APP/'runtime_checksums.json',{str(p.relative_to(APP)):sha(p) for p in APP.rglob('*') if p.is_file() and p.name!='runtime_checksums.json' and 'obj' not in p.relative_to(APP).parts and p.suffix not in ['.log','.map','.su']})
 write(ROOT/'offline_ready.json',dict(status='ABI26_CAR_PAIR_OFFLINE_READY_NOT_BOARD_TESTED',elf_sha256=sha(APP/'road_detail.elf'),post_proof_sha256=sha(ROOT/'post_complete.json'),preview=str(ROOT/'fixtures/road/preview.png'),scope_sha256=sha(ROOT/'scope.json'),sd_written=False));print('CAR_PAIR_TOOLS_STAGED_NOT_BOARD_TESTED',flush=True)
if __name__=='__main__':main()
