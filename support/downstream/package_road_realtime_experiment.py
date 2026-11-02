"""Compact local review package; truthful status follows physical evidence, never inferred FPS."""
from pathlib import Path
import hashlib,json,shutil,zipfile,sys
HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
APP=BASE/'road_qconv_app_20261027'
HLS=BASE/'road_qconv_r2_schedule_20261027'
FULL=BASE/'road_qconv_r2_full_20261027'
BOARD=BASE/'road_qconv_board_20261027'
QAT=BASE/'road_realtime_20261027'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    revision=sys.argv[1] if len(sys.argv)>1 else 'r1';assert revision in ['r1','r2']
    out=BASE/('road_realtime_review_20261027_'+revision);out.mkdir(exist_ok=False)
    quality=json.loads((QAT/'final_holdout_complete.json').read_text());assert not quality['passed']
    checked=json.loads((APP/'experiment_checksums.json').read_text())
    for n,h in checked.items():assert sha(APP/n)==h,n
    def copy(src,dst):
        dst=out/dst;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for n in ['arm_complete.json','arm_prepared.json','host_complete.json','arm_build.log','experiment_checksums.json','road_qconv.elf','display.bit','display.xsa','ps7_init.tcl','Xilinx.spec','camera_common.tcl','test_ram.tcl','scan_only.tcl','validate_physical.py','render.exe','YOLOv5_LICENSE']:
        copy(APP/n,'candidate/'+n)
    for d in ['source','runtime']:
        for p in (APP/d).rglob('*'):
            if p.is_file():copy(p,'candidate/'+str(p.relative_to(APP)))
    for n in ['offline_complete.json','build_board.tcl','timing_acceptance.txt','utilization.rpt','utilization_hierarchy.rpt','timing_summary.rpt','drc.rpt','clock_interaction.rpt']:
        copy(BOARD/n,'hardware_evidence/'+n)
    for n in ['checked.json','ip_complete.json','synthesis_checked.json','tb_all.csv','tb_rtl.csv','road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']:
        copy(HLS/n,'hls/'+n)
    copy(FULL/'full_csim_checked.json','hls/full_csim_checked.json')
    ip=json.loads((HLS/'ip_complete.json').read_text());assert sha(ip['archive'])==ip['archive_sha256'];copy(ip['archive'],'hls/catalog_ip.zip')
    for n in ['protocol.json','training_complete.json','selection_complete.json','final_candidate_frozen.json','fresh_protocol.json','fresh_selection.json','final_holdout_complete.json']:
        copy(QAT/n,'quality/'+n)
    copy(QAT/'fresh/complete.json','quality/fresh_complete.json')
    scripts=['road_qat_graph.py','train_road_qat.py','evaluate_road_qat.py','fetch_road_realtime_holdout.py','evaluate_road_realtime_holdout.py','verify_selected_road_qat_c.py','road_qconv_arm.c','road_qconv_arm.h','road_qconv_pack.c','prepare_road_qconv.py','prepare_road_qconv_model.py','check_road_qconv.py','prepare_road_qconv_r2.py','check_road_qconv_r2.py','package_road_qconv_ip.py','build_road_qconv_board.py','prepare_road_qconv_app.py','prepare_road_qconv_arm_app.py','prepare_road_qconv_physical.py','validate_road_qconv_physical.py','run_road_qconv_experiment.py','package_road_realtime_experiment.py']
    for n in scripts:copy(HERE/n,'reproduce_sources/'+n)
    copy(HERE.parents[1]/'实时检测加速实验_20261027.md','实时检测加速实验_20261027.md')
    archive=BASE/'road_hybrid_verified_20261027_r1.zip';assert sha(archive)=='4350f7bb5c4f150f5857f13730f2e185293edaae7f56f567afb78877e79019de';copy(archive,'rollback/verified_fp32_hybrid.zip')
    physical=APP/'experiment_session_r1.json';state=json.loads(physical.read_text()) if physical.exists() else dict(status='OFFLINE_READY_JTAG_SCAN_NO_TARGET_NOT_DOWNLOADED',hardware_access='Read-only JTAG target scan only',candidate_downloaded=False,sd_written=False,flash_written=False)
    if physical.exists():copy(physical,'physical/experiment_session_r1.json')
    if (APP/'physical_experiment_r1/validated.json').exists():copy(APP/'physical_experiment_r1/validated.json','physical/validated.json')
    if revision=='r2':
        assert state['status']=='EXPERIMENT_COMPLETE_FP32_HYBRID_RESTORED'
        for p in (APP/'physical_experiment_r1').rglob('*'):
            if p.is_file():copy(p,'physical/readback/'+str(p.relative_to(APP/'physical_experiment_r1')))
        for n in ['physical_summary.json','physical_validation.log','test_console.log','restore_hybrid.log']:
            copy(APP/n,'physical/'+n)
        copy(HERE.parents[1]/'整数检测加速实板报告_20261027.md','整数检测加速实板报告_20261027.md')
        copy(HERE/'summarize_road_qconv_physical.py','reproduce_sources/summarize_road_qconv_physical.py')
    if (APP/'scan_only.log').exists():copy(APP/'scan_only.log','physical/scan_only.log')
    readme='''# 7020 道路检测速度实验（非默认升级版）

本包包含全 60 卷积层的整数 FPGA 核心、ARM 程序、四类别候选模型、固定测试输入、综合布线证据及恢复包。

独立新测试集精度门槛未通过：夜间 mAP@0.5 原 FP32 为 24.23%，候选为 22.58%。不得把它宣传成识别效果更好的模型。实际板测状态见 status.json；没有实测记录就没有 FPS 结论。

工作目录为 E:/FPGA_Enhance_Work/road_qconv_app_20261027。脚本使用本机现有 Vivado/Vitis/HLS 2020.2、Python 环境和绝对路径；这是本机检查点，不是可任意解压运行的安装包。重建还需本机官方摄像头工程、独立 BSP 和项目数据。

run_road_qconv_experiment.py 只做临时 RAM 实验，结束或失败均尝试恢复 E:/FPGA_Enhance_Work/road_hybrid_20261027_r1。SD 卡和 Flash 不写入。rollback 中另附已验证原版本的完整归档。

内含 GPL-3.0 的 YOLOv5 衍生部分及原厂文件的原有版权声明。请保留对应许可。
'''
    (out/'README.md').write_text(readme,encoding='utf-8');(out/'status.json').write_text(json.dumps(dict(physical=state,accuracy_gate_passed=False,default_promotion_allowed=False),indent=2),encoding='utf-8')
    hashes={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()};(out/'checksums.json').write_text(json.dumps(hashes,indent=2))
    target=BASE/('road_realtime_review_20261027_'+revision+'.zip');assert not target.exists()
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(out)))
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    proof=dict(archive=str(target),bytes=target.stat().st_size,sha256=sha(target),status=state['status'],accuracy_gate_passed=False)
    (BASE/('road_realtime_review_20261027_'+revision+'.json')).write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2),flush=True)
if __name__=='__main__':main()
