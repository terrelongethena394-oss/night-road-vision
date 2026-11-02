"""Freeze illustrative road cases by labels/luminance, before board outputs."""
from pathlib import Path
import hashlib,shutil
from car_roi_delivery_common import BASE,ROOT,read,write,sha
from photo_station_core import DELIVERY

LAB=BASE/'road_scene_acceptance_20261031_r1'
PACK=DELIVERY/'道路场景验收'
DATA=ROOT/'confirmation/fresh'

def main():
    assert not LAB.exists(),'Preserve the frozen cases'
    LAB.mkdir();PACK.mkdir(exist_ok=False);(PACK/'测试照片').mkdir();(PACK/'标注').mkdir()
    rows=read(DATA/'manifest.json');used=set();selected=[]
    buckets=[('深暗少车',lambda r:r['timeofday']=='night' and r['mean_y']<20 and 1<=r['class_counts'][1]<=5),
        ('夜间多车',lambda r:r['timeofday']=='night' and r['class_counts'][1]>=10),
        ('一般夜景',lambda r:r['timeofday']=='night' and 20<=r['mean_y']<=48 and 1<=r['class_counts'][1]<=8),
        ('无车夜景',lambda r:r['timeofday']=='night' and r['class_counts'][1]==0)]
    fallback=('正常光参考',lambda r:r['timeofday']=='daytime' and 1<=r['class_counts'][1]<=8)
    for number,(title,rule) in enumerate(buckets,1):
        pool=[r for r in rows if rule(r) and r['group'] not in used]
        if not pool and number==4:title,rule=fallback;pool=[r for r in rows if rule(r) and r['group'] not in used]
        assert pool,title
        pool.sort(key=lambda r:hashlib.sha256(('road_board_acceptance_v1|'+r['name']).encode()).hexdigest())
        row=dict(pool[0]);used.add(row['group']);image=DATA/'images'/row['name'];label=DATA/'labels'/(Path(row['name']).stem+'.txt')
        assert sha(image)==row['image_sha256'] and sha(label)==row['label_sha256']
        image_copy=PACK/'测试照片'/f'{number:02d}_{title}_{row["name"]}';label_copy=PACK/'标注'/f'{number:02d}_{Path(row["name"]).stem}.txt'
        shutil.copy2(image,image_copy);shutil.copy2(label,label_copy)
        row.update(case=number,title=title,local_image=str(image),local_label=str(label),display_image=str(image_copy),display_label=str(label_copy))
        selected.append(row)
    protocol=dict(status='CASES_FROZEN_BEFORE_BOARD_OUTPUTS',selection='One deterministic hash-ranked case per label-count/luminance bucket; no detection results used to select.',
        scope='Illustrative engineering acceptance only; reused previously evaluated data, not a new independent accuracy study.',
        invariants='Same model/weights/confidence0.25/IoU0.5 matching; GUI aspect-preserving 800x480 input; actual board enhancement and raw-input detection; all selected cases reported.',
        metrics='Car-only TP/FP/FN at IoU0.5. Letterbox-aware ground-truth mapping. No enhancement-input detection superiority claim.',
        model_tuning=False,sd_write=False,source_manifest_sha256=sha(DATA/'manifest.json'),cases=selected)
    write(LAB/'protocol.json',protocol);write(PACK/'验收方案.json',protocol)
    lines=['# 道路场景验收','','数据来自项目已有BDD100K道路图片和标注。按亮度、车辆数量分组，以固定哈希顺序选图，选图时不看识别结果。',
        '本组图片用于实板功能与场景检查，数据此前已参与过评测，不是新独立测试集，不用这几张图片宣布准确率提升。','',
        '模型、阈值和SD卡固定。图像以工作台相同的等比例补边方式送到板上，结果由板上实际处理并读回。',
        '汽车标注按补边后的坐标映射，IoU达到0.5且一一匹配才计作正确检出；其余框计作误检，未匹配标注计作漏检。','',
        '| 编号 | 场景 | 汽车标注数 | 原始平均亮度 |','|---|---|---:|---:|']
    for r in selected:lines.append(f"| {r['case']:02d} | {r['title']} | {r['class_counts'][1]} | {r['mean_y']:.1f}/255 |")
    (PACK/'说明.md').write_text('\n'.join(lines),encoding='utf-8')
    print('ROAD_CASES_FROZEN',[(r['case'],r['title'],r['class_counts'][1],r['name']) for r in selected],flush=True)

if __name__=='__main__':main()
