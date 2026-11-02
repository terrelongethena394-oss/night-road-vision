from pathlib import Path
import json,hashlib,zipfile
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_detail_board_20261028_r1';APP=ROOT/'firmware';HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 s=read(ROOT/'session.json');assert s['status']=='PHYSICAL_VALIDATED_EXPERIMENT_RUNNING_DEFAULT_SINGLE_PASS';v=read(ROOT/'validated.json');a=v['timing']['0']['median_seconds'];b=v['timing']['1']['median_seconds'];proof=read(APP/'arm_complete.json')
 lines=['# 高细节实验版实板验收（2026-10-28）','',
  'ABI15实验程序已通过本轮软件／硬件数值及视频缓冲检查，结束时重新启动为**单次检测**，高细节模式可切换。SD卡和Flash未写入。', '',
  '## 结果','',
  '- 7个固定输入，每个分别运行单次和双次模式，共14组；全景和ROI检测头、解码、最终框与独立主机C结果符合原FP32数值契约。',
  '- 首例纯ARM与ARM／FPGA两路检测头、解码和最终框逐字节一致；首例全景全部86层通过主机C数值对照。',
  '- 固定图及摄像头两种模式的16字界面、Gamma像素、帧缓冲与主机绘制逐字节一致，VDMA错误字段为0。',
  '- 摄像头最新全景缩小图、中心ROI与读回的同一采集缓冲字节一致。冻结检测输入保持完整，结果画面与完成结果对应。','',
  '## 实测处理耗时','',
  '同一固定图片，FPGA加速开启，各4次，首次作为预热，剩余3次取中位数；不计JTAG数据传输、调试读回和屏幕展示等待。', '',
  '| 模式 | 预热 | 三次计时 | 中位耗时 |','|---|---:|---|---:|']
 for mode,title in [('0','单次全景检测'),('1','全景＋中心双次检测')]:
  t=v['timing'][mode];lines.append(f"| {title} | {t['warmup']:.3f}s | {', '.join(f'{x:.3f}s' for x in t['runs'])} | {t['median_seconds']:.3f}s |")
 lines += ['',f'本图高细节处理耗时约为单次的 {b/a:.2f} 倍。这是画质／检出与耗时的取舍，不能称为实时加速提升。','',
  '## 摄像头连续采样','',
  '每种模式先观察至少2个新结果，再做约20秒计数。左侧预览刷新与右侧检测快照频率不同；本表是短时实测，不代表长期稳定帧率。','',
  '| 模式 | 时间窗 | 完成检测数 | 检测更新 | 左侧预览 |','|---|---:|---:|---:|---:|']
 for r in v['live']:lines.append(f"| {'单次' if r['mode']==0 else '双次'} | {r['seconds']:.3f}s | {r['completed']} | {r['detection_hz']:.3f}Hz | {r['preview_hz']:.3f}Hz |")
 lines += ['', '## 固定图检测框数','', '框数用于核对推理流程，不是识别精度；不能以“框更多”单独判断效果。','', '| 输入 | 单次框数 | 双次框数 |','|---|---:|---:|']
 for c in proof['cases']:
  counts=[next(r['boxes']['count'] for r in v['fixed'] if r['name']==c['name'] and r['detail']==mode and r['pl']==1) for mode in [0,1]];lines.append(f"| {c['name']} | {counts[0]} | {counts[1]} |")
 lines += ['', '## 当前使用','',
  '当前默认单次检测：左边最新原图预览，右边增强显示的检测快照；识别使用原图。高细节开启后，多一次中心区域原图检测、过滤及结果合并，右侧标题为 `DETAIL X2 / EXPERIMENT`。', '',
  f"- 开启高细节：`{BASE.as_posix()}/road_detail_experiment_20261028/02_camera_detail_x2.cmd`。",
  f"- 恢复单次：`{BASE.as_posix()}/road_detail_experiment_20261028/03_camera_single_pass.cmd`。",
  f"- 恢复原ABI13：`{BASE.as_posix()}/road_detail_experiment_20261028/00_restore_previous.cmd`。",
  f"- ABI15断电后重载：`{BASE.as_posix()}/road_detail_experiment_20261028/01_load_experiment_default.cmd`。", '',
  '这些入口均为JTAG/RAM操作。新程序不包含新增训练的复核网络，消融未显示其收益，主检测器权重与bit未改变。当前上板验收不能替代实拍同场景明暗标注评测；公开图片上的mAP变化见原实验说明，误检增加的限制仍然存在。','',
  '## 复核记录','',f"- [数值与视频验证]({(ROOT/'validated.json').as_posix()})",f"- [运行收据]({(ROOT/'session.json').as_posix()})",f"- [ARM构建与内存布局]({(APP/'arm_complete.json').as_posix()})",f"- 全部原始读回保存在 `{(APP/'physical_r1').as_posix()}`。",'',
  f"当前ELF SHA256：`{sha(APP/'road_detail.elf')}`。",
  f"bit SHA256：`{sha(APP/'display.bit')}`。",
  f"权重 SHA256：`{sha(APP/'runtime/weights.f32')}`。"]
 report=WORK/'高细节检测实板验收_20261028.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8');(ROOT/'RESULTS_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 files=[ROOT/'session.json',ROOT/'validated.json',ROOT/'RESULTS_CN.md',ROOT/'startup.log',ROOT/'test.log',ROOT/'validation.log',ROOT/'activate_default.log']
 files += [p for p in APP.rglob('*') if p.is_file() and 'physical_r1' not in p.relative_to(APP).parts and 'obj' not in p.relative_to(APP).parts]
 archive=BASE/'road_detail_board_validated_20261028_r1.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in files:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 receipt=dict(report=str(report),archive=str(archive),archive_sha256=sha(archive),bytes=archive.stat().st_size,board_default_detail=0,sd_written=False);(ROOT/'report_complete.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print('DETAIL_BOARD_REPORT_SAVED',receipt,flush=True)
if __name__=='__main__':main()
