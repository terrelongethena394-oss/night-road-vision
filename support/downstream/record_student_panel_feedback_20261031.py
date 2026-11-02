"""Record user panel observation separately from automatic JTAG evidence."""
from pathlib import Path
import json,hashlib
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_student_fusion_20261031_r1/board_candidate'
WORKSPACE=Path(__file__).resolve().parents[2]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    receipt=read(ROOT/'actual_board_summary.json')
    assert receipt['status']=='ABI29_ACTUAL_BOARD_DISPLAY_FUSION_VERIFIED'
    feedback=dict(status='USER_CONFIRMED_PHYSICAL_PANEL_DISPLAY_NORMAL_RIGHT_BRIGHTER',
        answer='显示正常，右侧更亮',evidence=receipt['actual_evidence'],
        firmware_sha256=receipt['firmware_sha256'],
        scope='User observation of physicalLCD on fixedroad frame;does not establish independent imagequality or detectionaccuracy improvement.',
        hardware_programmed=False,sd_written=False)
    write(ROOT/'physical_panel_feedback.json',feedback)
    for p in [ROOT/'actual_board_summary.json',ROOT/'status_current.json',WORKSPACE/'当前学习增强运行版_20261031.json',WORKSPACE/'学习增强版上板验收_20261031/实际验收结果.json']:
        v=read(p);v['physical_panel_feedback']=feedback['status'];v['physical_panel_answer']=feedback['answer'];write(p,v)
    dest=WORKSPACE/'学习增强版上板验收_20261031'
    write(dest/'实物屏幕确认.json',feedback)
    report=dest/'验收说明.md';text=report.read_text(encoding='utf-8')
    old='本报告的“实际上板图”来自真实帧缓冲读回，不是拍摄实物LCD；实物观感还待用户观察。'
    new='本报告的“实际上板图”来自真实帧缓冲读回，不是拍摄实物LCD。用户已另行确认实物屏幕“显示正常，右侧更亮”；这一观察不等于独立画质或识别精度验证。'
    assert old in text;report.write_text(text.replace(old,new),encoding='utf-8')
    archive=read(ROOT/'board_archive_verified.json')
    note=dict(original_archive=archive['archive'],original_archive_sha256=archive['sha256'],
        archive_unchanged=True,post_archive_panel_feedback=str(ROOT/'physical_panel_feedback.json'),
        feedback_sha256=hashlib.sha256((ROOT/'physical_panel_feedback.json').read_bytes()).hexdigest(),
        reason='Preserve the verified archive;physical panel observation arrived after archival.',sd_written=False)
    write(dest/'归档后实物确认说明.json',note)
    print('ABI29_PHYSICAL_PANEL_FEEDBACK_RECORDED',json.dumps(feedback,ensure_ascii=True))
if __name__=='__main__':main()
