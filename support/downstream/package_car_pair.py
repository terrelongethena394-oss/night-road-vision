"""Archive the concrete compiled car A/B candidate without claiming board success."""
import hashlib,shutil,zipfile
from car_pair_common import *

def main():
 assert read(ROOT/'offline_ready.json')['status']=='ABI26_CAR_PAIR_OFFLINE_READY_NOT_BOARD_TESTED' and read(ROOT/'reader_complete.json')['not_board_verification']
 assert not (ROOT/'board_verified.json').exists()
 here=Path(__file__).resolve().parent
 for pattern in ['car_pair*.py','*car_pair*.py','road_car_pair*.*']:
  for p in here.glob(pattern):
   if p.is_file():shutil.copy2(p,ROOT/'source'/p.name)
 workspace=here.parents[1];report=workspace/'汽车专项对照版准备_20261030.md'
 report.write_text('''# 汽车专项对照版：已准备，尚未上板

用户选择“优先汽车，准备专项对照版上板验证”后创建独立ABI26工程。已验证ABI24工程保留，SD/Flash没有修改。此前四类综合验收的失败结论保留，本工程不再把卡车/公交车作为显示目标。

左边稳定模型，右边第4轮微调模型。两套模型分别运行相同冻结画面的四个未增强视图；图像增强只用于两侧相同的显示背景。网络结构仍保留四类输出，后处理只显示car类别。图像增强算法本轮未改，不能据此声称增强导致检测收益。

编译通过；汽车后处理1472组缓存结果与独立NumPy及既有C融合结果逐字节一致；离线屏幕预览已检查。回读检查器用模拟邮箱与真实C推理输出做过流程测试，并拒绝原图、权重元数据、检测框损坏的三个案例。这些不是开发板验收。

每次快照需要8次网络前向，预计408次PL调用，实测耗时待上板。验收将比较两个模型的全部8组解码输出、冻结输入、增强像素、汽车融合结果与LCD帧，并检查重复同一图片后结果一致。还将检查3次实际摄像头捕获；没有标注的摄像头画面不作为准确率证据。

预览案例为真实夜间道路028357c9-e07642f7.jpg，两侧背景完全相同。案例按结果选择用于展示，总体识别指标仍以全部320张独立暗光图片报告为准。完整验收结束后默认保留这张固定道路图，移动手掌不会改变图片；可再切换摄像头单帧。

工程：E:/FPGA_Enhance_Work/road_car_pair_20261030_r1

离线预览：E:/FPGA_Enhance_Work/road_car_pair_20261030_r1/fixtures/road/preview.png

首次上板使用03_full_acceptance.cmd；生成board_verified.json后才允许01_start_car_comparison.cmd和02_capture_again.cmd。04_fixed_road_photo.cmd显示固定道路图；00_restore_stable_ABI24.cmd恢复已验证稳定摄像头版。完整自动验收失败时会尝试恢复ABI24。当前等待开发板上电与JTAG连接确认。
''',encoding='utf-8')
 archive=BASE/'road_car_pair_ABI26_offline_ready_20261030.zip';assert not archive.exists()
 keep=[ROOT/'scope.json',ROOT/'offline_ready.json',ROOT/'post_complete.json',ROOT/'reader_complete.json',ROOT/'使用说明.md']+list(ROOT.glob('*.cmd'))
 for folder in ['firmware','tools','fixtures','source']:
  keep +=[p for p in (ROOT/folder).rglob('*') if p.is_file() and 'obj' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.log','.map','.su']]
 keep=sorted(set(keep));checks={p.relative_to(ROOT).as_posix():sha(p) for p in keep}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in keep:z.write(p,p.relative_to(ROOT).as_posix())
  import json
  z.writestr('package_checksums.json',json.dumps(checks,indent=2));z.write(report,'汽车专项对照版准备_20261030.md')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,digest in checks.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
 receipt=dict(status='CAR_PAIR_OFFLINE_PACKAGE_VERIFIED_NOT_BOARD_TESTED',archive=str(archive),sha256=sha(archive),elf_sha256=sha(APP/'road_detail.elf'),files=len(checks),sd_written=False);write(ROOT/'package_complete.json',receipt);write(workspace/'当前汽车专项对照版_20261030.json',dict(status='ABI26_OFFLINE_READY_WAITING_FOR_BOARD_POWER_CONFIRMATION',root=str(ROOT),report=str(report),active_verified_version=24,archive=str(archive),board_tested=False,sd_written=False));print('CAR_PAIR_OFFLINE_ARCHIVE_VERIFIED',receipt,flush=True)

if __name__=='__main__':main()
