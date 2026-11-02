"""Export metadata-selected real test crops; never filter using OCR predictions."""
from pathlib import Path
import hashlib, io, json, zipfile
import pyarrow.parquet as pq
from PIL import Image

SOURCE = Path('E:/FPGA_Enhance_Work/license_plate_20261026')
OUT = Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛/车牌检测图片_20261026')

def main():
    OUT.mkdir(exist_ok=False)
    records = json.loads((SOURCE/'data/manifest.json').read_text(encoding='utf-8'))
    prior = json.loads(Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026/plate_cases.json').read_text(encoding='utf-8'))
    used = {r['truth'] for r in prior}
    selected = [next(r for r in records if r['split']=='test' and r['text'].startswith(p) and r['text'] not in used)
                for p in ['苏','皖','沪','京','浙']]
    table = pq.read_table(SOURCE/'ccpd_crops_shard_0002.parquet', columns=['jpg'])
    originals = OUT/'原始照片'; originals.mkdir()
    exported = []
    for i, r in enumerate(selected, 1):
        data = table['jpg'][r['row']].as_py()['bytes']
        assert hashlib.sha256(data).hexdigest() == r['sha256']
        stem = f'{i:02d}_{r["text"]}'
        (originals/(stem+'.jpg')).write_bytes(data)
        image = Image.open(io.BytesIO(data)).convert('RGB')
        image.resize((960, round(image.height*960/image.width)), Image.Resampling.LANCZOS).save(OUT/(stem+'.png'))
        exported.append({**r, 'original_size':list(image.size), 'display_file':stem+'.png'})
    (OUT/'图片来源与标注.json').write_text(json.dumps(dict(
        source='CCPD, community cropped mirror zenitsu09/ccpd-ocr-recognition',
        original_project='https://github.com/detectRecog/CCPD',
        mirror='https://huggingface.co/datasets/zenitsu09/ccpd-ocr-recognition',
        selection='First remaining test image per province in frozen metadata order, excluding six previous replay plate identities; no OCR-based filtering.',
        transformations='Display PNGs resized to width960 preserving aspect ratio, no enhancement or super-resolution. Original JPG bytes retained.',
        note='New relative to previous board replay, but from an already evaluated public test set. Not a new blind test.',
        pictures=exported),ensure_ascii=False,indent=2),encoding='utf-8')
    rows='\n'.join(f'| {i} | {r["text"]} |  |  |  |' for i,r in enumerate(exported,1))
    (OUT/'使用说明与记录.md').write_text(f'''# 摄像头车牌测试图

打开顶层PNG，逐张放大显示或打印，车牌正对镜头并完整放入绿框，先在正常照明下停稳2秒，再记录三路。正确号码按CCPD原始数字标注解码，未根据模型输出来改标注或筛图。部分图片有倾斜、模糊，错误也请保留。

RAW：原图识别；NET：纯增强图识别；AUTO：最终保护图识别。请先测试正常亮度，再保持相机和图片位置不动调整照明。拍摄屏幕可能有反光、条纹，不能直接等同真实道路夜景。

| 图片 | 标注号码 | RAW | NET | AUTO |
|---|---|---|---|---|
{rows}

顶层PNG只按原比例放大，未增加细节或增强；原始照片目录保留原JPG。来源及哈希见图片来源与标注.json，CCPD许可附在目录中。这五张未在此前六张实板回放中使用，但属于已经做过整体离线评测的测试集，不能声称全新盲测。
''',encoding='utf-8')
    license_path = Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026/source_records/CCPD_LICENSE.txt')
    (OUT/'CCPD_LICENSE.txt').write_bytes(license_path.read_bytes())
    archive=OUT.with_suffix('.zip')
    assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps(dict(folder=str(OUT),labels=[r['text'] for r in exported],archive=str(archive)),ensure_ascii=True))

if __name__ == '__main__':main()
