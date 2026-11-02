"""Use actual ABI29 receipts only;archive evidence and report scope precisely."""
from pathlib import Path
import hashlib,json,zipfile,shutil,struct
import numpy as np
from PIL import Image,ImageDraw,ImageFont
BASE=Path('E:/FPGA_Enhance_Work');STUDY=BASE/'road_student_fusion_20261031_r1';ROOT=STUDY/'board_candidate';APP=ROOT/'firmware'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def image(p):
    a=np.fromfile(p,'<u4').reshape(240,400)
    return np.stack([a&255,a>>8&255,a>>16&255],2).astype(np.uint8)

def main():
    receipt=read(ROOT/'board_verified.json');assert receipt['status']=='ABI29_BALANCED_CAR_ACTUAL_BOARD_VERIFIED'
    out=Path(receipt['evidence']);old=Path(read(BASE/'road_car_balanced_20261030_r1/board_candidate/board_verified.json')['evidence'])
    packets={name:read(out/name/'verified.json') for name in ['photo_0','photo_1','photo_2','photo_3','camera_1','road_revisit']}
    assert all(p['physical_readback'] and p['status']=='ABI29_ACTUAL_BOARD_PACKET_PASS' for p in packets.values())
    comparisons=[]
    for case in ['photo_0','photo_1','photo_2','photo_3','road_revisit']:
        names=['source800.bgr','raw.u32','baseline.f32','boxes.f32','refiner_outputs.f32']+[f'raw_tile{i}.u32' for i in range(3)]+[f'decoded_base{i}.f32' for i in range(4)]
        if packets[case]['route_dark']:names+=[f'zoom{i}.u32' for i in range(3)]+[f'decoded_zoom{i}.f32' for i in range(3)]
        for n in names:assert (out/case/n).read_bytes()==(old/case/n).read_bytes(),(case,n)
        comparisons.append(dict(case=case,checked_files=len(names),all_byte_exact=True))
    enhanced_max=max(p['enhancement_max_abs'] for p in packets.values());neural=[n for p in packets.values() for n in p['detector_native_comparisons']]
    summary=dict(status='ABI29_ACTUAL_BOARD_DISPLAY_FUSION_VERIFIED',version=29,actual_evidence=str(out),packets=6,
      actual_detector_forward_comparisons=len(neural),actual_refiner_calls=sum(p['refiner_calls'] for p in packets.values()),
      enhancement_vs_host_c_max_abs=enhanced_max,detector_max_abs=max(p['max_abs'] for p in neural),detector_max_mean_abs=max(p['mean_abs'] for p in neural),
      static_raw_detection_vs_ABI28=comparisons,frame_byte_exact_all=True,repeat_fixed_source_deterministic=True,
      processing_seconds={name:p['processing_seconds'] for name,p in packets.items()},firmware_sha256=sha(APP/'road_detail.elf'),
      pl_bit_sha256=sha(APP/'display.bit'),main_weights_sha256=sha(APP/'runtime/weights.f32'),refiner_weights_sha256=sha(APP/'runtime/refiner_weights.f32'),
      student_parameters=411,student_weight_fnv=read(APP/'arm_complete.json')['student_weight_fnv'],
      quality_scope_correction_sha256=sha(STUDY/'quality_scope_correction.json'),
      accuracy_scope='Display-only enhancement;new enhanced-detection accuracy gain not demonstrated. Actual5fixedsource inputs/main outputs/boxes bitexact to priorABI28. Fullaccuracy previously measured in PC C,not all on physical board.',
      architecture='ARM classicalRetinex+411weightlearnedlowfrequencydisplaycorrection;PL unchanged YOLOconvolution accelerator;ARM smallboxrefiner.',
      final_screen=str(out/'road_revisit/lcd_readback.png'),physical_panel_feedback='PENDING_USER_OBSERVATION_FRAMEBUFFER_VERIFIED',hardware_programmed=True,sd_written=False)
    write(ROOT/'actual_board_summary.json',summary);write(ROOT/'status_current.json',summary)
    workspace=Path(__file__).resolve().parents[2];dest=workspace/'学习增强版上板验收_20261031';dest.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
    canvas=Image.new('RGB',(1200,680),(15,15,15));d=ImageDraw.Draw(canvas)
    for row,case in enumerate(['photo_0','photo_1']):
        ims=[image(out/case/'raw.u32'),image(old/case/'enhanced.u32'),image(out/case/'enhanced.u32')]
        boxes=np.fromfile(out/case/'boxes.f32','<f4').reshape(-1,6)
        for col,(label,a) in enumerate(zip(['原图','原增强 ABI28','新增强 ABI29'],ims)):
            im=Image.fromarray(a);draw=ImageDraw.Draw(im)
            for x1,y1,x2,y2,score,cls in boxes:draw.rectangle((x1,y1,x2,y2),outline=(0,230,255),width=1)
            canvas.paste(im,(400*col,40+row*320));d.text((400*col+5,row*320+5),f'夜间道路{row+1}：{label}',font=font,fill='white')
        d.text((5,285+row*320),'三列叠加相同原图检测框；框数增加不代表本次增强提高检测精度。',font=small,fill='white')
    d.text((5,650),'图像来自实际上板JTAG读回；天空噪点、压缩色块与原图模糊仍有残留。',font=small,fill='white')
    canvas.save(dest/'实际上板_原图旧增强新增强.png')
    shutil.copy2(out/'road_revisit/lcd_readback.png',dest/'当前板上帧缓冲读回.png')
    write(dest/'实际验收结果.json',summary)
    q=read(STUDY/'quality_scope_correction.json');diagnostic=read(STUDY/'detector_diagnostic.json')['scores']['low']
    times='\n'.join(f'| {name} | {p["processing_seconds"]:.3f} | {p["detector_forward_count"]} | {p["candidate_cars"]} |' for name,p in packets.items())
    report=f'''# 学习增强版ABI29实际上板验收

本次已通过JTAG实际下载并运行。最终保留固定夜间道路图：左侧原图、右侧新增强图，两侧叠加同一组原图车辆检测框。它是单帧测试，移动手掌不会改变当前固定图片。SD卡和Flash未改。

## 实际核对

- 6个实际读回包：两张夜间道路图、灰图、黑图、摄像头单帧、再次测试第一张道路图。
- {len(neural)}次主检测网络输出与独立电脑C核对，最大误差{summary['detector_max_abs']:.8f}，最大平均误差{summary['detector_max_mean_abs']:.9f}，在既定容差内。
- {summary['actual_refiner_calls']}次ARM小框修正网络实际调用已核对。
- 新增强输出相对电脑C最大像素误差：{enhanced_max}。6个帧缓冲均与独立渲染结果逐字节一致。
- 5个固定输入测试相对ABI28的源图、原图裁剪、主网络输出、修正输出及最终检测框逐字节一致。摄像头单帧已与该帧自己的电脑C参考核对，不与此前不同场景的摄像头帧比较。
- 摄像头测试后再次测试第一张固定图，结果一致。

| 测试包 | 板上单次处理秒数 | 主网络前向次数 | 检测框数 |
|---|---:|---:|---:|
{times}

这些时间来自板上计时，不含JTAG传图、读回和电脑验收时间。它仍是单帧检测，不是实时视频检测；框数不是正确检出数量。灰图/黑图零框只说明这两个控制样例，没有证明所有背景都不会误检。

## 增强和检测的实际关系

增强由ARM执行：论文光照估计和保细节处理，加上本项目训练的411参数残差CNN，只混合平滑后的亮度修正，保留已有纹理和色差。车辆检测主卷积继续由原有FPGA PL加速；小框修正网络在ARM。未将411参数增强网络硬化到PL，不能写成“本次已实现FPGA神经网络增强加速”。

新图中路面和部分暗部更亮，直接使用小网络造成的过亮有所缓和；天空噪点、压缩色块和源图模糊仍可见。本报告的“实际上板图”来自真实帧缓冲读回，不是拍摄实物LCD；实物观感还待用户观察。

把新增强图直接送入固定单视图检测器的64张已用暗光开发图对照：AP50 {diagnostic['raw']['ap50']*100:.2f}%→{diagnostic['enhanced']['ap50']*100:.2f}%，TP {diagnostic['raw']['tp']}→{diagnostic['enhanced']['tp']}，FP {diagnostic['raw']['fp']}→{diagnostic['enhanced']['fp']}，精确率{diagnostic['raw']['precision']*100:.2f}%→{diagnostic['enhanced']['precision']*100:.2f}%。误检增加，不能只看AP或框数。板上因此继续使用原图检测；本次没有证明增强导致独立检测准确率提高。

## 画质数字的范围更正

原20张成对开发图中3张共享的正常曝光参考图，与直接训练图片缩放后的像素相同。原始结果已保留并标记，不能作为独立证明。剔除该参考组后，剩余{q['remaining_images']}张/{q['remaining_reference_groups']}组的开发回归：PSNR {q['remaining_per_image']['current']['psnr']:.2f}→{q['remaining_per_image']['fusion']['psnr']:.2f}，SSIM {q['remaining_per_image']['current']['ssim']:.3f}→{q['remaining_per_image']['fusion']['ssim']:.3f}。这些图片此前也反复用于开发，且教师预训练来源未证明与它们完全独立，所以不能称为新独立画质测试。

教师是原作者公开的Retinexformer预训练参考；本项目另训练了411参数学生。完整Transformer没有部署到开发板。训练和选择中失败的原始学生、联合损失学生、单独光照估计器等实验均保留，未替换为成功结论。

## 运行与恢复

当前固件：{APP/'road_detail.elf'}。
当前实际证据：{out}。
板上固件SHA256：{summary['firmware_sha256']}。

运行目录中的01可重新加载并采摄像头一帧，02再采一帧，03加载固定道路图，04切原图/增强显示，06执行完整验收；00恢复ABI28至摄像头待拍预览。它们都只运行于RAM。旧board_waiting.json是历史连接失败记录，以board_verified.json、actual_board_summary.json和status_current.json为准。
'''
    (dest/'验收说明.md').write_text(report,encoding='utf-8')
    write(workspace/'当前学习增强运行版_20261031.json',summary)
    archive=BASE/'road_student_fusion_ABI29_board_verified_v2_20261031.zip';assert not archive.exists();files={}
    for p in ROOT.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.o' and 'archive_verified' not in p.name and 'native' not in p.relative_to(ROOT).parts:
            files['board_candidate/'+p.relative_to(ROOT).as_posix()]=p
    for p in dest.iterdir():
        if p.is_file():files['report/'+p.name]=p
    for name in ['protocol.json','complete.json','visual_review.json','data_overlap_audit.json','quality_scope_correction.json','detector_diagnostic.json','detector_diagnostic_protocol.json','comparison.png']:
        files['study/'+name]=STUDY/name
    student=BASE/'road_retinex_student_20261031_r2';chosen=read(student/'selected.json')['chosen']
    for name in ['protocol.json','history.json','selected.json','training_selection.json','c_proof/complete.json','c_proof/weights.f32']:
        files['student/'+name]=student/name
    for p in (student/'source').iterdir():
        if p.is_file():files['student/source/'+p.name]=p
    files['student/model.pt']=student/'frozen'/chosen/'model.pt';files['student/frozen.json']=student/'frozen'/chosen/'frozen.json'
    for name in ['prepare_retinexformer_reference_20261031.py','download_retinexformer_weight_20261031.py','retinexformer_reference_runtime.py','study_retinexformer_reference_20261031.py','build_student_fusion_arm_20261031.py','prove_retinex_student_20261031.py','prove_student_fusion_20261031.py','evaluate_student_fusion_detector_20261031.py','audit_student_data_20261031.py','clarify_student_quality_scope_20261031.py',Path(__file__).name]:
        files['workflow/'+name]=Path(__file__).with_name(name)
    teacher=BASE/'retinexformer_reference_20261031_r1'
    for name in ['source_manifest.json','weight_manifest.json','source/LICENSE.txt','source/README.md','evaluation/detection_result.json','evaluation/paired_diagnostic.json']:
        files['pc_reference/'+name]=teacher/name
    hashes={n:sha(p) for n,p in files.items()}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in files.items():z.write(p,name)
        z.writestr('SHA256_MANIFEST.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    receipt=dict(status='ABI29_ACTUAL_BOARD_EVIDENCE_ARCHIVE_VERIFIED',archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(files)+1,all_member_sha_and_crc_verified=True,sd_written=False)
    write(ROOT/'board_archive_verified.json',receipt);write(dest/'归档校验.json',receipt)
    print('ABI29_ACTUAL_BOARD_FINALIZED',json.dumps(dict(summary=summary,archive=receipt)),flush=True)
if __name__=='__main__':main()
