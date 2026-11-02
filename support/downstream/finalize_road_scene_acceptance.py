from pathlib import Path
import numpy as np
from prepare_road_scene_acceptance import LAB,PACK
from photo_station_core import verify_return,STAGING
from car_roi_delivery_common import read,write,sha

def main():
    complete=read(LAB/'complete.json');assert complete['status']=='FOUR_FIXED_ROAD_CASES_ACTUAL_BOARD_VERIFIED'
    assert {r['case'] for r in complete['cases']}=={1,2,3,4} and not (STAGING/'jtag.lock').exists()
    totals=dict(cars_annotated=0,tp=0,fp=0,fn=0);diagnostics=[]
    for r in complete['cases']:
        packet=Path(r['source_result']['packet_evidence']);v=verify_return(packet,packet.parent/'prepared',kind=5)
        assert v['frame_byte_exact'] and v['input_byte_exact'] and v['model_fingerprints_checked']
        for key in totals:totals[key]+=r[key]
        g=np.asarray(r['ground_truth_board400'],np.float32).reshape(-1,5)
        p=np.fromfile(packet/'boxes.f32','<f4').reshape(-1,6)
        for i,good in enumerate(r['prediction_correct']):
            if good:continue
            if len(g):
                wh=np.maximum(0,np.minimum(g[:,3:5],p[i,2:4])-np.maximum(g[:,1:3],p[i,:2]));inter=wh.prod(1)
                area=(g[:,3:5]-g[:,1:3]).prod(1);pa=(p[i,2:4]-p[i,:2]).prod()
                iou=inter/(area+pa-inter+1e-7);best=float(iou.max())
            else:best=0
            diagnostics.append(dict(case=r['case'],prediction=i,best_iou_to_car_label=best,confidence=float(p[i,4])))
    text='''# 观察与下一步

本轮完成的是四个固定道路场景的真实板上功能检查，源图、增强像素、检测框和LCD帧缓冲均已实际读回并校验。所有选定场景都保留，包含漏检和误检。

## 图像增强

我检查了四张真实回传的原图/增强对照。车道线、路面与部分背景变得更容易看见，但深暗少车图的路面有明显色块，天空与暗部噪声被放大，灯光周围的光晕也更明显。一般夜景图同样存在提亮偏强的现象。平均亮度增加不能等同于细节恢复。

下一轮画质优化应先限制深暗区域的最大增益，保护灯光，减少色块与噪声；选择参数时同时看暗处可见性和画面自然度。

## 汽车检测

这一组图片里的标注汽车大多很小，在400×240处理图上有的仅几像素高。多车和一般夜景仍有明显漏检与定位误差。无车图片本次没有汽车误报，但单张无车图片不能代表所有无车场景。

后续识别改进应优先比较路面区域分块、原始分辨率小目标输入和小目标训练样本。使用开发集选择方案，再单独验证；这四张已曝光的验收图不能重新称为新独立测试集。

当前检测输入仍是原图。上述增强画质问题与检测误差分别记录，本轮没有增强后检测准确率提升的结论。

模型、检测阈值、FPGA位流和SD卡均保持原版。本组结果应作为功能验证及问题分析材料。
'''
    (PACK/'观察与改进优先级.md').write_text(text,encoding='utf-8')
    record=dict(status='ROAD_SCENE_PACK_FULL_READBACK_AND_ANNOTATIONS_CHECKED',cases=4,example_totals=totals,
        false_positive_iou_diagnostics=diagnostics,all_cases_reported=True,new_accuracy_gain_claimed=False,
        models_changed=False,sd_written=False,summary_sha256=sha(PACK/'实板验收结果.md'),contact_sha256=sha(PACK/'四场景核对总览.png'))
    write(LAB/'final_verified.json',record);write(PACK/'交付核对.json',record)
    print('ROAD_SCENE_PACK_VERIFIED',totals,flush=True)

if __name__=='__main__':main()
