"""Archive audit evidence, preserving the accepted board and its files."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
ROOT=Path('E:/FPGA_Enhance_Work/road_bright_detector_audit_20261030_r1')
STAGE=WORK/'阶段展示与收尾_20261030'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=read(ROOT/'result.json');checked=read(ROOT/'verified.json')
assert result['status']=='REJECT_KEEP_RAW_NN_ENHANCED_DISPLAY'
assert checked['result_sha256']==sha(ROOT/'result.json')
assert all(v==0 for v in checked['gpu_minus_previous_c_raw_control'].values())

for name in ['check_bright_detector_audit_20261030.py','finalize_bright_audit_20261030.py',
             'road_accuracy_common.py','road_numpy_eval.py','road_arm_common.py',
             'shadowlift_lab.py','launch_road_cuda.py']:
    shutil.copy2(HERE/name,ROOT/'source'/name)
guide=STAGE/'下一步与分工.md'
text=guide.read_text(encoding='utf-8')
marker='\n## 后续已完成：增强输入专项核查\n'
if marker in text:text=text.split(marker)[0]
text+=marker+'''
已在电脑完成同模型配对测试：320张暗光图＋96张较亮对照图。

- 主要候选只把全图输入换成当前ABI27增强图，三路细节仍使用原图；其余设置不变。
- 暗光汽车AP50：46.46%→45.53%；精确率45.74%→42.16%；召回率48.26%→48.37%。
- TP 1331→1334，但FP 1579→1830。整体未通过预定验收门槛。
- 320张原图对照的AP、精确率、召回率、TP/FP/FN与此前实际C结果完全一致；另抽查6路实际C输入，坐标最大差小于0.0001像素、分数差小于0.000003。
- 所以当前继续保留原图识别、增强显示，板上程序、SD卡、Flash均未改动。

这批数据已经使用过，本次只能称为配对效果核查。结论不意味着所有增强方法都无效，也不代表每张图片都会变差；图示同时保留了增益和退步案例。若未来要证明增强有助于识别，需要在训练数据上让检测器适配增强后的分布，并用未参与选择的标注数据验证，不能用本次失败结果继续挑参数并当作新盲测。

本次结果见本目录“增强输入专项核查/实验结论.md”。接下来的交付重点仍是实际摄像头固定场景记录、稳定演示、报告与视频，而不是把未达标的输入路径上板。
'''
guide.write_text(text,encoding='utf-8')

selected=['protocol.json','result.json','verified.json','predictions.json','timing.json',
          'image_identity.json','label_sha256.json','per_image_differences.json',
          '实验结论.md','指标.csv','diagnostic_examples.png']
files=[ROOT/name for name in selected]+sorted((ROOT/'source').glob('*.py'))
manifest={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files}
identity=dict(status='AUDIT_ARCHIVED_REJECT_CANDIDATE_PRESERVE_ABI27',
    source_root=str(ROOT),sha256=manifest,
    dependencies='Uses existing model, dataset, C runtime and Python environment identified by protocol hashes. This is an evidence archive, not an SD boot image.',
    board_access=False,sd_written=False)
manifest_path=ROOT/'archive_manifest.json'
manifest_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding='utf-8')
archive=ROOT.parent/'road_bright_detector_audit_20261030_r1.zip'
assert not archive.exists(),'Preserve any previous archive'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files+[manifest_path]:z.write(p,str(p.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
receipt=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
             members=len(files)+1,crc_and_member_sha256_verified=True,
             board_access=False,sd_written=False)
(ROOT/'archive_verified.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
# Refresh the demonstration manifest to include the additional evidence folder.
stage_hashes={str(p.relative_to(STAGE)).replace('\\','/'):sha(p) for p in STAGE.rglob('*')
              if p.is_file() and p.name!='manifest.json'}
(STAGE/'manifest.json').write_text(json.dumps(dict(purpose='Existing measured evidence plus paired enhancement audit',
    sha256=stage_hashes,board_access=False,sd_written=False),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=True))
