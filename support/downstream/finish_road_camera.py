"""Package camera integration after physical fixed/live-frame validation."""
from pathlib import Path
import csv,statistics,shutil,json,hashlib,zipfile,subprocess,sys
from build_road_camera import ROOT,HERE,NN,read,write,sha
WORK=HERE.parents[1]

def cadence(path):
    rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(path.open())];assert len(rows)==31
    assert all(r['error']==r['dma_read']==r['dma_write']==0 and r['state'] in [1,2] for r in rows)
    assert all(b['completed']>=a['completed'] and b['preview']>=a['preview'] for a,b in zip(rows,rows[1:]))
    seconds=(rows[-1]['wall_ms']-rows[0]['wall_ms'])/1000;assert seconds>10
    completed=rows[-1]['completed']-rows[0]['completed'];preview=rows[-1]['preview']-rows[0]['preview'];assert completed>=2 and preview>=30
    cycles={}
    for r in rows:
        if not r['had_pause']:cycles[r['completed']]=(r['detect_lo']+r['detect_hi']*2**32)/r['hz']
    assert len(cycles)>=2 and all(0<t<30 for t in cycles.values())
    return dict(measured_wall_seconds=seconds,preview_updates=preview,preview_hz=preview/seconds,completed_detections=completed,completed_detection_hz=completed/seconds,
      distinct_unpaused_cycle_seconds=cycles,unpaused_detection_median_seconds=statistics.median(cycles.values()),all_dma_and_error_checks_zero=True,
      note='Read-only500ms mailbox polling. Host-wall cadence; not sensor exposure FPS. Detect timer excludes snapshot acquisition/result-copy/display, includes cooperative preview inside forward, excludes acknowledged debug pause.')

def main():
    physical=read(ROOT/'physical_complete.json');o=read(ROOT/'offline_complete.json');assert physical['elf_sha256']==o['elf_sha256']
    before=cadence(ROOT/'cadence_before_snapshots.csv');final=cadence(ROOT/'cadence_final.csv')
    live=[read(ROOT/f'live_snapshot_{i:02d}/validated.json') for i in [1,2]]
    fixed=read(ROOT/'board_r2_fixed/validated.json');oldfull=read(ROOT/'board_fixed_first/validated.json')
    assert len(oldfull['all_layers'])==86 and len(fixed['heads'])==3 and all(v['kind']=='live' for v in live)
    assert sha(ROOT/'obj/road_fp32.c.o')==read(ROOT/'revision_r2.json')['kernel_object_sha256']
    outcome=dict(status='LIVE_CAMERA_PREVIEW_AND_FROZEN_RESULT_PHYSICALLY_VALIDATED',elf_sha256=o['elf_sha256'],weights_sha256=o['weights_sha256'],cadence_before=before,cadence_final=final,
      fixed_reference=fixed,live_reference=live,live_inputs_changed=sha(ROOT/'live_snapshot_01/result400.u32')!=sha(ROOT/'live_snapshot_02/result400.u32'),
      current_mode='Live camera, left latestrawpreview, rightlatestcompleted FP32detection snapshot',source_correspondence_verified=True,
      raw_only_no_enhancement=True,sd_written=False,flash_written=False,physical_panel_visual_confirmation='Not yet confirmed byuser',
      accuracy_boundary='Current camera snapshots only verify implementation; no labeled real-camera dark-scene accuracy claim.',neural_compute='ARM Cortex-A9, no new PL CNN acceleration')
    write(ROOT/'camera_result.json',outcome)
    # Portable RAM-only installer, no static-image test/readback on normal startup.
    original=(ROOT/'install_camera_r2_test.tcl').read_text();prefix=original[:original.index(' rc_test {')]
    prefix=prefix.replace('set out $root/board_fixed_first\nif {$argc>=1} {set out [file normalize [lindex $argv 0]]}\nif {[file exists $out]} {error "Preserve first readback"}\n','')
    tail=''' mwr 0x13800070 0
 mwr 0x1380006c 0
 mwr 0x1380000c 3
 set ready 0
 for {set i 0} {$i<600} {incr i} {
  after 100
  rc_check
  if {[word 0x138000cc]>=2 && [word 0x138000e0]==0} {set ready 1;break}
 }
 if {!$ready} {error "Live detector did not produce results"}
 disconnect
 puts "ROAD_CAMERA_LIVE_READY"
} why opts]} {
 puts stderr "ROAD_CAMERA_FAILED $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit 0
'''
    installer=prefix+tail
    import tkinter
    assert int(tkinter.Tcl().call('info','complete',installer))==1
    assert '$out' not in installer and 'rc_test ' not in installer and 'rc_packet ' not in installer
    (ROOT/'start_camera_live.tcl').write_text(installer,encoding='ascii')
    essential=['road_camera.elf','display.bit','display.xsa','ps7_init.tcl','camera_common.tcl','start_camera_live.tcl','runtime/weights.f32']
    manifest={name:sha(ROOT/name) for name in essential};write(ROOT/'runtime_checksums.json',manifest)
    verifier='''from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent
for n,h in json.loads((r/'runtime_checksums.json').read_text()).items():
    assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
print('ROAD_CAMERA_RUNTIME_HASHES_PASS')
'''
    (ROOT/'verify_runtime.py').write_text(verifier,encoding='ascii')
    cmd='''@echo off
cd /d "%~dp0"
"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0verify_runtime.py"
if errorlevel 1 exit /b 1
call "E:\\Xilinx\\Vitis\\2020.2\\bin\\xsct.bat" "%~dp0start_camera_live.tcl"
echo Require ROAD_CAMERA_LIVE_READY; XSCT exit code alone is insufficient.
pause
'''
    (ROOT/'00_start_camera_ram.cmd').write_text(cmd,encoding='ascii')
    p=subprocess.run([sys.executable,str(ROOT/'verify_runtime.py')],capture_output=True,text=True,check=True);assert 'HASHES_PASS' in p.stdout
    report=f'''# 摄像头预览与道路检测接入验收（2026-10-27）

## 当前已实现

已将原FP32道路检测器接回OV5640，并在7020/V3.9、800×480屏幕上验证。左侧是最近采集的400×240原图预览；右侧是最近完成检测的输入快照，其框仅对应右侧图片。界面明确标注SNAP编号、快照AGE和DETECT耗时，不把旧框画到新预览上。

当前板卡已恢复连续运行。该版本只使用原图检测，没有启用增强支路，没有写SD或Flash。模型与上一轮已选FP32权重相同，**这次完成的是系统接入，不是新模型精度提升，也不是FPGA检测加速**。

## 实测更新速度

最后一段只读采样持续{final['measured_wall_seconds']:.2f}秒，预览增加{final['preview_updates']}次，约**{final['preview_hz']:.2f}次/秒**；检测结果增加{final['completed_detections']}次，约**{final['completed_detection_hz']:.2f}次/秒**。

采样覆盖的未暂停检测周期耗时中位数约**{final['unpaused_detection_median_seconds']:.2f}秒**。该计时从预处理到NMS，包含期间预览任务，扣除明确的调试暂停；不含采样取得、结果复制和最终显示提交。因此不能直接把它与此前2.55秒的计时定义作速度提升对比。

VIEW是应用预览更新频率，不是OV5640曝光帧率；AGE从CPU完成采样平均时开始，不是传感器曝光时间戳。右侧仍是低频检测快照，不能称为实时目标跟踪。

## 正确性证据

- 新增卷积行间/算子间协作回调后，电脑端8个用例的全部86层、解码、NMS与原版C输出逐字节相同。
- 800×480 BGR到400×240 RGB字平均，在黑、白、随机图上逐字节核对；现场也读取未再被摄像头写入的采集槽，平均结果与预览400图的384000字节完全相同。
- 第一版实板固定图核对全部86层、三尺度检测头、解码、框及完整LCD帧；另核对黄昏图和黑图，黑图确认旧框清除。
- 随后修正调试暂停恰落在检测开始前的计时边界。R1源码/ELF保留在revisions/r1；R2的检测内核对象文件与R1完全相同，重新通过固定图和两份真实摄像头快照核对。
- 两份真实快照均把“右侧实际检测输入”送入原版电脑C参考，比较三个头、全部解码输出和NMS；使用读回的真实框与界面元数据重新渲染，1152000个帧缓冲字节均一致。
- 摄像头ID=0x5640、屏幕ID=0x7084，检查VDMA读写状态及停泊槽。最终连续采样中未出现DMA或应用错误。

现场两份快照的框数为{live[0]['boxes']['count']}和{live[1]['boxes']['count']}。框数不代表精度；未对这些室内画面人工标注，不据此宣称检测准确。手掌不是本模型的类别，镜头前没有完整行人/车辆时可能没有框。

## 如何看屏幕

1. 移动手掌，确认左侧持续更新；这只检查预览。右侧按较慢节奏换图，SNAP应变化、AGE随等待增加后在新结果时回落。
2. 核对红蓝物体的颜色。若要试识别，应对准完整人物、车辆，或已有包含这些类别的道路照片；类别仅person、car、truck、bus。
3. 低照度效果还需要同场景正常光/暗光对照。当前未证明增强能提高检测，也没有从未标注的摄像头画面计算mAP。

## 程序与恢复

目录：`{ROOT.as_posix()}`。

`00_start_camera_ram.cmd`先核对运行文件哈希，再通过JTAG加载已验证的bit、ELF和权重，启动连续模式。仅RAM下载，不写SD；断电后需要重新加载。它不是SD启动包。

原固定图片恢复入口：`E:/FPGA_Enhance_Work/road_lcd_static_20261027/00_install_ram.cmd`。

源代码在source/；road_fp32.c仅加入协作服务回调，计算仍在ARM；road_camera_main.c负责不同快照/结果缓冲区、调度、暂停和计时；road_camera_io.c复用已验证的摄像头/VDMA驱动；road_camera_draw.c保证框仅画在右侧快照。GPL-3.0及厂商驱动版权声明保留。

当前ELF SHA256：`{o['elf_sha256']}`。

权重 SHA256：`{o['weights_sha256']}`。

本轮原始证据：board_r2_fixed/、live_snapshot_01/、live_snapshot_02/、cadence_final.csv、camera_result.json。actual_framebuffer.png是板上帧缓冲读回，不是实体屏幕照片。实体屏幕的移动与颜色检查尚待用户确认。
'''
    (ROOT/'摄像头接入验收_20261027.md').write_text(report,encoding='utf-8');(WORK/'摄像头接入验收_20261027.md').write_text(report,encoding='utf-8')
    for p in [WORK/'实板模型对比_20261027.md',WORK/'道路感知项目当前进度_20261026.md']:
        if p.exists():
            with p.open('a',encoding='utf-8') as f:f.write(f'\n\n2026-10-27摄像头追加：已接入左侧实时更新预览、右侧对应冻结快照检测，当前连续运行，原FP32权重未换。末段实测预览{final["preview_hz"]:.2f}Hz、检测更新{final["completed_detection_hz"]:.2f}Hz，未启用增强或改SD。详见[摄像头接入验收](摄像头接入验收_20261027.md)。\n')
    release=ROOT/'release';release.mkdir(exist_ok=False)
    for name in essential+['runtime_checksums.json','verify_runtime.py','00_start_camera_ram.cmd','YOLOv5_LICENSE','摄像头接入验收_20261027.md','camera_result.json','offline_complete.json','host_complete.json','revision_r2.json']:
        d=release/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,d)
    shutil.copytree(ROOT/'source',release/'source')
    # Include one current paused-frame receipt and a snapshot image; all full raw evidence stays in ROOT.
    shutil.copytree(ROOT/'live_snapshot_02',release/'physical_live_evidence',ignore=shutil.ignore_patterns('host_reference'))
    files={p.relative_to(release).as_posix():sha(p) for p in sorted(release.rglob('*')) if p.is_file()};write(release/'manifest.json',dict(status='CAMERA_INTEGRATION_PHYSICALLY_VALIDATED_NO_SD_WRITE',files=files))
    archive=ROOT.with_name(ROOT.name+'_verified.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(release.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(release))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,h in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
    write(ROOT/'release.json',dict(status='CAMERA_INTEGRATION_ARCHIVED_LIVE_RUNNING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),cadence=final,
       current_elf_sha256=o['elf_sha256'],sd_written=False,enhancement_enabled=False,report=str(WORK/'摄像头接入验收_20261027.md')))
    print('ROAD_CAMERA_LIVE_INTEGRATION_FINALIZED',final,flush=True)
if __name__=='__main__':main()
