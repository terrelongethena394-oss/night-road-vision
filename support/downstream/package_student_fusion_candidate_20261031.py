"""Concrete RAM-only candidate handoff, explicit waiting/verified status."""
from pathlib import Path
import shutil,hashlib,json,zipfile
BASE=Path('E:/FPGA_Enhance_Work');STUDY=BASE/'road_student_fusion_20261031_r1';ROOT=STUDY/'board_candidate';APP=ROOT/'firmware'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=ROOT/'tools/balanced_board_entry.py';s=p.read_text(encoding='utf-8').replace("mode=='restore27'","mode=='restore28'").replace('manual_20261030_','manual_20261031_');p.write_text(s,encoding='utf-8')
    deps=read(ROOT/'runtime_dependencies.json');deps.update({str(p):sha(p) for p in (ROOT/'tools').glob('*.py')});deps[str(STUDY/'quality_scope_correction.json')]=sha(STUDY/'quality_scope_correction.json');write(ROOT/'runtime_dependencies.json',deps)
    actions={'00_restore_ABI28.cmd':'restore28','01_start_camera.cmd':'start_camera','02_capture_again.cmd':'capture','03_start_fixed_photo.cmd':'start_photo','04_raw_vs_enhanced.cmd':'raw_enh','05_detection_views.cmd':'models','06_full_acceptance.cmd':'verify'}
    for name,mode in actions.items():
        (ROOT/name).write_text('@echo off\r\n"E:\\FPGA_Enhance_Work\\nn_env312\\Scripts\\python.exe" "%~dp0tools\\balanced_board_entry.py" '+mode+'\r\npause\r\n',encoding='ascii')
    doc='''# 学习增强候选 ABI29

此目录为独立、可恢复的JTAG内存运行包，不写SD卡或Flash。当前是否完成实际上板，请查看board_verified.json；reader_smoke.json和simulated_reader_tests仅为电脑模拟验收脚本测试，不能当作上板证据。

增强：原论文的光照估计和原有保细节增强，加上本项目训练的411参数残差CNN；只融合平滑后的亮度差，保留原有细节和颜色。增强及小框修正网络在ARM运行，车辆检测卷积由原有PL加速。原图检测输入、主网络权重、多视图及小框修正均保持ABI28配置。不声称本次增强提高识别准确率。

屏幕左侧原图、右侧新增强图。左右叠加相同的原图检测结果。模式05比较原有4视图与自适应多视图检测，背景相同；它不是增强前后检测准确率对照。

00恢复原ABI28到RAM；01加载新程序并采摄像头一帧；02再采一帧；03加载新程序并测试固定道路图片；04切换原图/增强显示；05查看检测视图对照；06执行完整实际上板验收。图像测试完成后暂停并保留画面，不是实时检测。

需现有E盘工具链和依赖目录，归档并非全新电脑独立安装包。JTAG下载器连接且开发板独立供电后运行。重新上电运行SD原程序；本包未改动SD。

来源复查发现，原20张成对开发图中3张共享的正常曝光目标与训练图片缩放后相同。剔除该参考组后，剩余17张/7组的电脑C开发回归为PSNR14.37→18.24、SSIM0.589→0.766。剩余图片也已反复用于开发，且不能证明与原教师训练来源独立，因此这些数字不是新的独立画质证明。请以quality_scope_correction.json为准，原始结果保留。天空噪点、压缩色块和原图模糊仍然存在。
'''
    (ROOT/'使用说明.md').write_text(doc,encoding='utf-8')
    archive=BASE/'road_student_fusion_ABI29_candidate_v2_20261031.zip';assert not archive.exists()
    files={}
    for p in ROOT.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.o' and 'archive_verified' not in p.name:files['board_candidate/'+p.relative_to(ROOT).as_posix()]=p
    for name in ['protocol.json','complete.json','visual_review.json','comparison.png','detector_diagnostic.json','detector_diagnostic_protocol.json','data_overlap_audit.json','quality_scope_correction.json']:
        if (STUDY/name).exists():files['study/'+name]=STUDY/name
    student=BASE/'road_retinex_student_20261031_r2'
    for name in ['protocol.json','history.json','selected.json','training_selection.json','c_proof/complete.json','c_proof/weights.f32']:
        files['student/'+name]=student/name
    for p in (student/'source').iterdir():
        if p.is_file():files['student/source/'+p.name]=p
    chosen=read(student/'selected.json')['chosen']
    files['student/frozen/model.pt']=student/'frozen'/chosen/'model.pt'
    files['student/frozen/frozen.json']=student/'frozen'/chosen/'frozen.json'
    teacher=BASE/'retinexformer_reference_20261031_r1'
    for name in ['source_manifest.json','weight_manifest.json','source/LICENSE.txt','evaluation/detection_result.json','evaluation/paired_diagnostic.json']:
        files['pc_reference/'+name]=teacher/name
    manifest={name:sha(p) for name,p in files.items()}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in files.items():z.write(p,name)
        z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    receipt=dict(status='ABI29_COMPILED_CANDIDATE_ARCHIVED_BOARD_VERIFICATION_PENDING',archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(manifest)+1,archive_integrity_checked=True,
      firmware_sha256=sha(APP/'road_detail.elf'),hardware_programmed=False,sd_written=False)
    write(ROOT/'candidate_archive_verified.json',receipt)
    workspace=Path(__file__).resolve().parents[2];out=workspace/'学习增强候选_20261031';out.mkdir(exist_ok=True)
    shutil.copy2(STUDY/'comparison.png',out/'电脑端画质对照.png')
    shutil.copy2(ROOT/'使用说明.md',out/'候选说明.md');write(out/'候选状态.json',receipt)
    print('ABI29_CANDIDATE_ARCHIVE_VERIFIED',json.dumps(receipt),flush=True)
if __name__=='__main__':main()
