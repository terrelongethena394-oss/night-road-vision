"""Release the verified same-frame neural enhancement plus normal-light protection."""
from pathlib import Path
import json,csv,hashlib,zipfile,shutil
ROOT=Path('E:/FPGA_Enhance_Work/multinex_camera_protected_fast_20261026')
BASE=ROOT.parent
QUALITY=BASE/'camera_quality_mean_20261026'
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    off=read(ROOT/'offline_camera.json');policy=read(ROOT/'quality_policy.json');q=read(QUALITY/'complete.json')
    assert q['accepted'] and policy==q and policy['selected']['dark']==32 and policy['selected']['normal']==48
    assert off['normal_protection'] and sha(ROOT/'camera.elf')==off['elf_sha256']
    cached=read(BASE/'multinex_camera_cached_20261026/board_deployed.json')
    assert sha(ROOT/'camera.bit')==cached['bit_sha256']==off['bit_sha256']
    cases=[]
    for d in sorted((ROOT/'board_quality').iterdir()):
        r=read(d/'validation.json')
        assert r['status']=='ACTUAL_HOST_PHOTO_ENHANCEMENT_EXACT' and r['source_kind']=='host_photo'
        assert r['rgb_output_exact'] and r['lcd_pixels_exact'] and r['protection']['protected_pixels_exact']
        assert r['read_dma_error']==r['write_dma_error']==0
        cases.append(dict(id=d.name,**r))
    assert len(cases)==3 and {r['protection']['alpha'] for r in cases}=={0,224,256}
    live=read(ROOT/'live_snapshot/validation.json')
    assert live['status']=='ACTUAL_LIVE_CAMERA_ENHANCEMENT_EXACT' and live['source_kind']=='live_camera'
    assert live['rgb_output_exact'] and live['lcd_pixels_exact'] and live['capture_reduction_exact']
    assert live['protection']['protected_pixels_exact'] and live['read_dma_error']==live['write_dma_error']==0
    with (ROOT/'live_cadence.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==11 and all(int(r[k])==0 for r in rows for k in ('read_error','write_error','error'))
    seconds=(int(rows[-1]['elapsed_ms'])-int(rows[0]['elapsed_ms']))/1000
    frames=int(rows[-1]['sequence'])-int(rows[0]['sequence']);assert seconds>=9.5 and frames>=60
    hz=frames/seconds
    result=dict(status='LIVE_CAMERA_NORMAL_PROTECTION_BOARD_VERIFIED',camera_shape=[480,800],enhancement_shape=[240,400],
        completed_frames=frames,measured_seconds=seconds,display_update_hz=hz,live_snapshot=live,photo_cases=cases,
        policy=policy['selected'],bit_sha256=sha(ROOT/'camera.bit'),elf_sha256=sha(ROOT/'camera.elf'),
        cached=True,sd_written=False,recognition_enabled=False,quality_regression=q,
        notes='Same r4d neural weights/bit. ARM output controller selects keep/full/mix from same-frame mean luminance; pure network output remains separately auditable. PC40condition quality scores and four actual board frames are distinct evidence. Existing20pairs contain only10unique normal reference scenes and were previously seen; not a clean blind/generalization benchmark. Noise/temporal flicker/recognition require separate evaluation.')
    (ROOT/'board_deployed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=ROOT/'quality_evidence';evidence.mkdir(exist_ok=True)
    for name in ('summary.json','per_image.csv','complete.json','protocol.json','selection.json'):
        shutil.copy2(QUALITY/name,evidence/name)
    shutil.copy2(BASE/'camera_quality_20261026/protocol.json',evidence/'camera_format_protocol.json')
    summary=read(QUALITY/'summary.json')
    def s(condition,method):return next(r for r in summary if r['condition']==condition and r['method']==method)
    original,pure,old=s('low','Input'),s('low','Multinex'),s('low','OldNN8')
    protected,normal=s('low','ProtectedMultinex'),s('normal','ProtectedMultinex')
    doc=f'''# 摄像头画质保护版：已验证并上板

当前为同一帧的原图/保护后增强对比。网络仍是已验证的Multinex整数模型，权重和PL位流没有改变；增加的是ARM端正常光输出保护，不称重新训练了增强网络。

右侧标题：**KEEP**表示保持原图，**ENH**表示完整神经网络增强，**MIX**表示两者混合。根据当前帧8位平均亮度Y选择：Y≤32全增强、Y≥48保持原图，中间线性混合。这里的数字不是照度lux。纯网络输出仍单独保留，以便核查。

## 已有照片回归（电脑端、匹配400×240相机格式）

| 暗光输入方法 | 平均PSNR↑ | 平均SSIM↑ |
|---|---:|---:|
| 原图 | {original['psnr']:.3f} | {original['ssim']:.4f} |
| 旧NN8 | {old['psnr']:.3f} | {old['ssim']:.4f} |
| 新网络纯输出 | {pure['psnr']:.3f} | {pure['ssim']:.4f} |
| 新网络+保护 | {protected['psnr']:.3f} | {protected['ssim']:.4f} |

20张正常亮度输入全部保持原图，不再过度增亮；暗光20张中19张完整增强、1张轻度混合。正常光相对未量化参考的SSIM约{normal['ssim']:.4f}，误差来自输入RGB565及缩放等，并非网络新增细节。不能把正常光旁路带来的高分说成神经网络本身性能提升。

规则用原our485的12对验证图选择，已有20对LOL-v2照片只作回归；其中正常参考只有10个不同SHA，存在重复场景，且此前已被查看。不是全新盲测；公开模型的预训练重合也未排除。曾尝试的p95规则伤害4幅背光暗图，已拒收，未部署。详见本机camera_quality_20261026、camera_quality_p95_20261026、camera_quality_mean_20261026各完整记录。

预处理按真实链路：同中心裁剪800×480、RGB565零扩展、2×2整数平均400×240；正常参考采用同裁剪/平均但不施加传感器量化。比较未用正常参考图替换暗光输入。

## 真正的开发板验证

三张固定照片分别覆盖alpha=0、224、256，共288000像素：输入校验正确，PL纯网络输出逐字节匹配冻结独立C++，保护输出匹配独立整数公式，LCD两半匹配同一帧，采集/显示DMA无错误。它们是电脑传入DDR的照片，明确不是摄像头拍摄。

另一个真实摄像头帧96000像素也通过完整采集缓冲2×2平均、纯网络输出、保护输出和实际LCD DDR核对。测试后已恢复连续摄像头。连续{seconds:.3f}秒完成{frames}次更新，约**{hz:.2f}次/秒**；网络计算仍约79毫秒。这里是增强显示更新次数，不是传感器帧率或精确的镜头到屏幕延迟。保持800×480传感器输入和400×240网络分辨率。

ARM采用缓存管理，保护层以等价打包整数运算及端点复制减少额外开销；FINAL是CPU显示输入，调试暂停前再flush供JTAG回读。与未经保护的缓存版约9.31次/秒相比，本次实际速度以以上数字为准，不隐去性能开销。

## 保留的边界

本次解决了已有样本上的正常光过度增强问题，未证明任意光照都正确。全帧亮度规则可能漏掉逆光局部暗区；暗光噪声、视频闪烁、曝光切换和文字细节仍需独立实拍检验。没有进行新的识别率测试，不能宣称一定帮助识别。摄像头保留官方自动曝光，亮度不是实测照度。

SD卡未改，旧静态版、无保护缓存版及恢复包全部保留。JTAG下载易失，关电后不会自动恢复当前程序。恢复入口start_multinex_camera.tcl；board_quality是实板静态照片记录，live_snapshot是真实摄像头记录，actual_lcd_ddr.png都由DDR直接回读生成，不是屏幕拍照。
'''
    (ROOT/'画质保护版结果.md').write_text(doc,encoding='utf-8')
    (ROOT/'README.md').write_text('# 已上板的摄像头画质保护版\n\n见[画质保护版结果](画质保护版结果.md)。\n\n当前运行摄像头，左RAW，右KEEP/ENH/MIX，SD未修改。\n',encoding='utf-8')
    shutil.copy2(HERE/'finish_camera_quality.py',ROOT/'finish_camera_quality.py')
    selected=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in
        ('.bit','.elf','.xsa','.tcl','.py','.json','.md','.csv','.spec') and p.name not in ('runtime_manifest.json','release.json')]
    for name in ('app_src','quality_inputs','quality_evidence','board_quality','live_snapshot'):
        selected.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    selected=sorted(set(selected));manifest=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in selected]
    (ROOT/'runtime_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=BASE/'multinex_camera_quality_verified_20261026.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in selected:z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'runtime_manifest.json','runtime_manifest.json')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (ROOT/'release.json').write_text(json.dumps(dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,crc_ok=True),indent=2),encoding='utf-8')
    print('CAMERA_QUALITY_RELEASED',hz,sha(archive),flush=True)
if __name__=='__main__':main()
