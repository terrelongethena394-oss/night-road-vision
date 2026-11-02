"""Archive only an actually running, independently verified cached camera app."""
from pathlib import Path
import json,csv,hashlib,zipfile,shutil
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_cached_20261026')
HERE=Path(__file__).resolve().parent
STATIC=ROOT.parent/'multinex_fast_static_r4d_20261026'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    offline=read(ROOT/'offline_camera.json');static=read(STATIC/'board_deployed.json')
    assert sha(ROOT/'camera.bit')==offline['bit_sha256']==static['bit_sha256']
    assert sha(ROOT/'camera.elf')==offline['elf_sha256']
    assert sha(ROOT/'ps7_init.tcl')==sha(STATIC/'ps7_init.tcl')
    snapshots=[read(ROOT/n/'validation.json') for n in ('snapshot_01','snapshot_02')]
    for s in snapshots:
        assert s['status']=='ACTUAL_LIVE_CAMERA_ENHANCEMENT_EXACT'
        assert s['rgb_output_exact'] and s['capture_reduction_exact'] and s['lcd_pixels_exact']
        assert s['profile']['cache_enabled'] and s['resumed_sequence']>s['sequence']
        assert s['read_dma_error']==s['write_dma_error']==0
    with (ROOT/'live_cadence.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==11
    assert all(int(r[k])==0 for r in rows for k in ('read_error','write_error','error'))
    t=(int(rows[-1]['elapsed_ms'])-int(rows[0]['elapsed_ms']))/1000
    frames=int(rows[-1]['sequence'])-int(rows[0]['sequence']);assert t>=9.5 and frames>20
    assert all(int(b['sequence'])>int(a['sequence']) for a,b in zip(rows,rows[1:]))
    status=dict(status='LIVE_CAMERA_CACHED_BOARD_VERIFIED',camera_shape=[480,800],enhancer_shape=[240,400],
        completed_frames=frames,measured_seconds=t,display_update_hz=frames/t,
        snapshots=snapshots,bit_sha256=sha(ROOT/'camera.bit'),elf_sha256=sha(ROOT/'camera.elf'),
        cached=True,sd_written=False,recognizer_enabled=False,
        old_static_release_preserved=True,
        limits='Software enhanced-display update cadence, not measured photon-to-panel latency or sensor FPS. Same original model/weights. Default auto exposure; normal-light over-brightening/highlight clipping observed. Physical red/blue check previously confirmed on uncached build; cached LCD DDR independently verified.')
    (ROOT/'board_deployed.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    doc=f'''# 摄像头增强与延迟优化结果

当前开发板运行缓存优化版：OV5640采集800×480，经2×2 RGB平均形成400×240图像，再由PL执行完整Multinex整数增强。800×480屏幕左右两幅400×240显示同一帧的RAW和ENH，比例保持一致；上、下黑边是布局留白。

## 实板确认

- 摄像头ID0x5640、屏幕ID0x7084；用户已确认先前摄像头版运动更新及颜色正常。
- 缓存版两个真实帧，共192000像素的PL输出与冻结独立C++参考逐字节一致。实际采集缓冲的2×2平均与模型输入也精确，实际LCD DDR左右图与输入/输出分别精确；不是只看主机预期图。
- 两次调试暂停后均恢复持续采集/增强。连续{t:.3f}秒完成{frames}次更新，即约**{frames/t:.2f}次/秒**，采集和显示DMA错误均为0。
- 增强核本身约{np.mean([s['kernel_seconds'] for s in snapshots])*1000:.1f}毫秒。第一版禁用缓存时抽样完整循环218.5毫秒（约4.6次/秒）；启用正确缓存维护后，第一样本循环100.7毫秒，连续平均以以上计数为准。该比较未降低分辨率或修改模型权重。

ARM缓存优化：mailbox所在段保持不缓存以支持JTAG同步；CPU读取完成采集帧前invalidate，PL开始前flush输入，PL完成后invalidate输出，LCD换帧前flush显示缓冲。采集与显示缓冲独立，采集writer换到另一park缓冲后才读取上一完整帧，避免直接复制正在写入的图像。

## 边界和接下来的重点

这仍达不到原先轻量流式模型的响应速度，约79毫秒的完整网络计算是当前主要下限。连续显示更新次数不是传感器帧率，也不是严格的镜头到屏幕延迟测量。进一步降延迟需要网络/硬件改造或在画面细节与分辨率间取舍，应单独评估。

实际正常光预览中增强侧偏亮、部分高光过曝，不能声称所有场景画质都改善。下一步先测正常光/暗光、噪声和细节保持，再加入正常光保护。之后才用同一个识别器，比较原图与增强图的真实识别率，不能把变亮等同于识别更好。

当前无识别核、摄像头自动曝光仍为官方默认。SD卡未写入，已验证静态增强包与此前版本保留。JTAG运行可拔下载器但须保留独立供电；断电后本程序不会自行恢复，除非另行制作SD启动镜像。

恢复脚本start_multinex_camera.tcl（重新下载易失bit/ELF）。调试snapshot_multinex_camera.tcl会在完整增强帧后暂停、回读真实数据，再自动恢复。snapshot_01/02的actual_lcd_ddr.png来自实际DDR，不是屏幕拍照；其中可能含摄像头拍到的个人画面，仅保存在本机。
'''
    (ROOT/'摄像头与延迟优化结果.md').write_text(doc,encoding='utf-8')
    (ROOT/'README.md').write_text('# 摄像头缓存优化版（已实板验证）\n\n见[摄像头与延迟优化结果](摄像头与延迟优化结果.md)。\n',encoding='utf-8')
    shutil.copy2(HERE/'finish_multinex_camera.py',ROOT/'finish_multinex_camera.py')
    files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in
        ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.csv','.spec') and p.name not in ('runtime_manifest.json','release.json')]
    for n in ('app_src','snapshot_01','snapshot_02'):
        files.extend(p for p in (ROOT/n).rglob('*') if p.is_file())
    files=sorted(set(files))
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]
    (ROOT/'runtime_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=ROOT.parent/'multinex_camera_cached_verified_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'runtime_manifest.json','runtime_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True),indent=2),encoding='utf-8')
    print('CACHED_CAMERA_RELEASED',frames/t,sha(archive),flush=True)
if __name__=='__main__':main()
