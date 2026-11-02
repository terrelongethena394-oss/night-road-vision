"""Save camera milestone and local start/capture/restore entries."""
import shutil,sys,zipfile
from camera_snapshot_tools import *
HERE=Path(__file__).resolve().parent
WORK=Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛')
PY='E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe'
def stage():
 src=ROOT/'tools';src.mkdir(exist_ok=True)
 for pattern in ['*camera_snapshot*.py','road_capture_views.*']:
  for p in HERE.glob(pattern):
   if p.resolve()!=(src/p.name).resolve():shutil.copy2(p,src/p.name)
 commands={
  '01_start_camera_and_capture.cmd':[str(src/'camera_snapshot_entry.py'),'start'],
  '02_capture_again.cmd':[str(src/'camera_snapshot_entry.py'),'capture'],
  '00_restore_fixed_photo.cmd':[str(OLD/'road_accuracy_entry.py'),'start','5'],
  '03_run_full_acceptance.cmd':[str(src/'run_camera_snapshot_acceptance.py')],
 }
 for name,args in commands.items():
  line='@echo off\r\n"'+PY+'" '+' '.join('"'+x+'"' for x in args)+'\r\nset "task_exit=%errorlevel%"\r\npause\r\nexit /b %task_exit%\r\n';(ROOT/name).write_text(line,encoding='ascii',newline='')
 proof=read(ROOT/'board_verified.json') if (ROOT/'board_verified.json').exists() else None
 state='已完成三组800整帧输入对照和三次真实摄像头采集的板上验收。' if proof else '已编译，板上验收尚未完成；快捷启动入口会等待真实验收收据。'
 execution='图像采集、裁图、增强和检测均已在板上执行；PC仅用于JTAG启动、触发和读回核验。' if proof else '图像采集、裁图、增强和检测设计为板上执行；实板验收尚未完成，当前不能声称本轮摄像头流程已运行成功。'
 timings=''
 if proof:timings=f"三次真实拍摄的处理时间为 {min(r['processing_seconds'] for r in proof['camera_results']):.2f}–{max(r['processing_seconds'] for r in proof['camera_results']):.2f} 秒；另有采集／裁图准备时间，且不含JTAG读回核验。"
 text=f'''# 摄像头单帧增强与识别 ABI24（2026-10-30）

{state}

目录：`{ROOT.as_posix()}`。

## 操作

开发板独立供电，保持OV5640、屏幕和JTAG连接，使用此前已验证的JTAG启动配置。

- `01_start_camera_and_capture.cmd`：下载本版并自动拍摄一次。启动时只上传程序、位流和权重，不上传测试照片。
- `02_capture_again.cmd`：在本版已运行时重新拍摄一帧。拍摄后四次检测使用同一帧；请先把目标放好，再点击。
- `00_restore_fixed_photo.cmd`：恢复此前已验证的ABI23固定暗光道路图。
- `03_run_full_acceptance.cmd`：重新执行完整验收，包含三组已知图片以及三次摄像头采集。失败后尝试恢复ABI23。

显示左侧是本次冻结原图与单次检测框，右侧是同一帧增强显示及多视图融合框。画面保持不动是预期行为，移动手掌不会让已经拍下的照片改变，需要再次拍摄。手掌也不属于模型类别。

这是拍照检测，不是视频实时检测。{timings}

## 本轮真正改变的部分

上版三个局部输入由PC预先生成；本版由ARM从同一张800×480摄像头帧生成全景和三个局部输入，再执行四次检测。VDMA切换到另一写入缓冲后，保存上一完整帧；计算和显示冻结结果期间不再切换预览写缓冲。读取的旧VDMA缓冲必须与独立保存帧逐字节一致，四个检测输入也必须与该帧的独立NumPy裁图一致。

PL卷积核、检测权重、框融合和传统Retinex增强参数保持原样。ARM负责裁图、其余网络算子、调度、融合和增强显示，PL复用原卷积加速核，每次拍摄共204次加速核调用。

## 证据与限制

- 15组电脑像素用例核对全景平均、三窗口、BGR／RGB顺序、输入不变和输出边界。
- 三组已知800×480输入先在ARM裁图，再对四个网络输出及最终框与实际ABI23结果逐字节比较。
- 真实摄像头帧必须与停放的VDMA原始缓冲逐字节一致；处理前后整帧哈希相同，避免混用不同时间画面。
- 摄像头四个网络输出与独立C FP32参考按预先固定容差核对：最大绝对差不超过0.001，平均不超过0.00002。融合框和显示帧采用逐字节核对。
- 日常再次拍摄不重复在PC执行检测网络。{execution}

原320张低亮度图片的离线汽车AP提升证据仍保留在ABI23报告中；它不能直接当作本机OV5640实拍准确率。本轮没有采集带标注的摄像头测试集，也未证明提亮本身提升识别。若镜头对准桌面而不是完整汽车／道路目标，框数不能当作模型准确率。

当前通过JTAG启动／触发，尚未制作本版SD独立启动，也没有接入板载拍照按键。SD卡和Flash未修改。旧ABI23和ABI18恢复目录保留。工具使用本机E盘Xilinx2020.2、Python和旧版目录，不能直接移动到其他电脑运行。
'''
 (ROOT/'使用与验证说明.md').write_text(text,encoding='utf-8');(WORK/'摄像头单帧版进度_20261030.md').write_text(text,encoding='utf-8')
 write(WORK/'当前摄像头单帧版_20261030.json',dict(status='ABI24_BOARD_VERIFIED' if proof else 'ABI24_COMPILED_AWAITING_BOARD',directory=str(ROOT),camera_on_board_cropping=True,board_verified=bool(proof),neural_weights_unchanged=True,not_realtime=True,sd_written=False))
 print('CAMERA_SNAPSHOT_ENTRIES_STAGED',bool(proof),flush=True)
def archive():
 stage();verified=(ROOT/'board_verified.json').exists();tag='board_verified' if verified else 'offline_ready';target=BASE/f'road_camera_snapshot_ABI24_{tag}_20261030.zip';assert not target.exists()
 files=[p for p in ROOT.rglob('*') if p.is_file() and 'obj' not in p.relative_to(ROOT).parts and '__pycache__' not in p.relative_to(ROOT).parts and p.name!='package_manifest.json']
 manifest={p.relative_to(ROOT).as_posix():sha(p) for p in files};write(ROOT/'package_manifest.json',manifest)
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files+[ROOT/'package_manifest.json']:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for name,digest in manifest.items():assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==digest
 write(BASE/f'camera_snapshot_ABI24_{tag}_package_20261030.json',dict(path=str(target),bytes=target.stat().st_size,sha256=sha(target),all_hashes_and_crc_verified=True,board_verified=verified,sd_written=False))
 print('CAMERA_SNAPSHOT_ARCHIVE_VERIFIED',target,sha(target),flush=True)
if __name__=='__main__':{'stage':stage,'archive':archive}[sys.argv[1]]()
