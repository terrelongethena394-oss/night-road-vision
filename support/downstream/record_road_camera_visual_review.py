"""File-only review: preserve currently running board and immutable raw evidence."""
from pathlib import Path
import json,hashlib,zipfile,shutil
import numpy as np
from build_road_camera import ROOT,HERE,read,write,sha
WORK=HERE.parents[1]

def main():
    confirm=dict(status='USER_CONFIRMED_PHYSICAL_PANEL_LIVE_MOVEMENT_COLORS_AND_PERIODIC_RESULT_UPDATES',
       user_answer='左侧持续更新、颜色正常，右侧隔几秒换图',paired_lighting_test='Deferred explicitly byuser; keepcurrentrunningstate',no_hardware_operations=True)
    write(ROOT/'user_visual_confirmation.json',confirm)
    p=ROOT/'physical_complete.json';physical=read(p);physical['physical_panel_confirmation']=confirm['user_answer'];physical['lighting_test_deferred_by_user']=True;write(p,physical)
    p=ROOT/'camera_result.json';result=read(p);result['physical_panel_visual_confirmation']=confirm['user_answer'];result['lighting_test_deferred_by_user']=True
    boxes=np.fromfile(ROOT/'live_snapshot_02/boxes400.f32','<f4').reshape(-1,6);cars=[b.tolist() for b in boxes if int(b[5])==1];assert cars
    review=dict(status='QUALITATIVE_REAL_CAMERA_FALSE_POSITIVE_RETAINED',source='live_snapshot_02',input_sha256=sha(ROOT/'live_snapshot_02/result400.u32'),
        framebuffer_sha256=sha(ROOT/'live_snapshot_02/frame.bgr'),model_outputs=boxes.tolist(),
        observation='Visible clothing/body area in the analyzed snapshot is labeled CAR at approximately41percent confidence. This is an observed falsepositive, not a complete GTannotation or a dataset mAP estimate.',
        pipeline='Physical savedheads/decoded/NMS agree with hostC on exactly the same camera input. Therefore the observed CAR prediction is reproduced bythe model, not an identified ARM/PL data-conversion discrepancy.',
        disposition='Retain weights and confidence threshold; retain rawbadcase. Need labeled representative person/vehicle scenes and appropriate negative samples for accuracy evaluation before furthermodelchanges.',
        current_scope='Rawcamera+ARMFP32 detector; no enhancement used in this observation',board_changed=False)
    write(ROOT/'real_camera_false_positive.json',review);result['qualitative_false_positive']=review;write(ROOT/'camera_result.json',result)
    text='''

## 用户确认与已观察到的误检

用户已确认：“左侧持续更新、颜色正常，右侧隔几秒换图”。因此实体屏幕的预览运动、颜色和检测快照更新已得到确认。用户目前不便布置明暗对照，明确要求保留当前运行状态；本次记录不再操作板卡。

第二份实拍快照中，衣物/身体区域被标成CAR，置信度约41%。这是需要保留的误检，不能因为采集与部署核对通过就认为模型在实拍中识别效果达标。电脑对同一份输入复算也输出该框，说明该现象由模型输出复现，并非已发现的板端数据转换错误。

该例是定性观察，没有完整人工框标注，不由此计算实拍准确率或mAP。保持当前权重和阈值，保留原始输入、输出和误检证据。后续需要带标注的代表性人物/车辆场景及负样本，才能评价和改进泛化。

明暗对照暂缓；不改变用户的照明和板卡状态。当前程序继续运行，SD卡未改。
'''
    for p in [ROOT/'摄像头接入验收_20261027.md',WORK/'摄像头接入验收_20261027.md']:
        s=p.read_text(encoding='utf-8').replace('实体屏幕的移动与颜色检查尚待用户确认。','实体屏幕的移动与颜色检查已获用户确认，详见追加记录。');p.write_text(s+text,encoding='utf-8')
    release=ROOT/'release'
    for name in ['camera_result.json','user_visual_confirmation.json','real_camera_false_positive.json','摄像头接入验收_20261027.md']:shutil.copy2(ROOT/name,release/name)
    files={p.relative_to(release).as_posix():sha(p) for p in sorted(release.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    write(release/'manifest.json',dict(status='CAMERA_INTEGRATION_PHYSICALLY_AND_VISUALLY_VERIFIED_FALSEPOSITIVE_DOCUMENTED',files=files))
    previous=read(ROOT/'release.json');archive=ROOT.with_name(ROOT.name+'_verified_r1.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(release.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(release))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    previous['previous_archive']=dict(path=previous['archive'],sha256=previous['sha256']);previous.update(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
         user_visual_confirmation=True,real_camera_false_positive_documented=True,lighting_test_deferred=True,no_new_hardware_operations=True)
    write(ROOT/'release.json',previous)
    handoff=WORK/'当前运行检查点_摄像头道路检测_20261027.md'
    handoff.write_text(f'''# 当前运行检查点（2026-10-27）

当前程序：`{(ROOT/'road_camera.elf').as_posix()}`，SHA256 `{previous['current_elf_sha256']}`。

板卡处于连续运行：左侧最新相机预览，右侧最近完成检测的冻结快照；原FP32权重、ARM检测、原图支路，未启用增强。本次用户已确认移动、颜色及快照更新正常。

末段实测预览约6.56Hz、检测结果更新约0.36Hz，检测耗时中位数约2.79秒。计时定义见验收文档，不当作实时跟踪。

用户当前不方便布置明暗对照，要求保留运行状态。不要为了补该测试而擅自暂停、换程序或改SD。本轮SD/Flash均未写；SD自启动问题仍待后续处理。

已保留实际误检：第二份摄像头快照的衣物/身体区域被判为CAR约41%，电脑复算一致。部署正确性通过不等于模型泛化达标；明暗条件下的实拍精度还未验证。

最新资料包：`{archive.as_posix()}`。

验收记录：[摄像头接入验收](摄像头接入验收_20261027.md)。
''',encoding='utf-8')
    print('CAMERA_VISUAL_CONFIRMATION_AND_FALSEPOSITIVE_ARCHIVED_BOARD_UNCHANGED',sha(archive),flush=True)
if __name__=='__main__':main()
