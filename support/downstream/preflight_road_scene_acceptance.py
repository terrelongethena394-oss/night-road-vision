"""Offline annotation geometry/matching checks; no board processing claim."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_road_scene_acceptance import LAB,PACK
from run_road_scene_acceptance import mapped_truth
from road_numpy_eval import correct
from photo_station_core import prepare_photo
from car_roi_delivery_common import read,write,sha

def main():
    tests=LAB/'metric_tests';tests.mkdir(exist_ok=True)
    label=tests/'fixture.txt';label.write_text('1 .5 .5 .5 .6\n',encoding='ascii')
    g=mapped_truth(dict(local_label=str(label),class_counts=[0,1,0,0]),dict(resized_size=[800,450],padding_xy=[0,15]))
    assert np.allclose(g,[[1,100,52.5,300,187.5]],rtol=0,atol=1e-5)
    p=np.array([[100,52.5,300,187.5,.9,1],[100,52.5,300,187.5,.8,1]],np.float32)
    ok,matched=correct(p,g,np.array([.5],np.float32));assert int(ok.sum())==1 and matched[0]=={0}
    assert not correct(p,np.empty((0,5),np.float32),np.array([.5],np.float32))[0].any()
    assert correct(np.empty((0,6),np.float32),g,np.array([.5],np.float32))[0].shape==(0,1)
    rows=read(LAB/'protocol.json')['cases'];canvas=Image.new('RGB',(800,560),(12,18,28));d=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15);preflight=[]
    for at,row in enumerate(rows):
        assert sha(row['display_image'])==row['image_sha256']
        meta=prepare_photo(row['display_image'],LAB/'preflight'/f'case{row["case"]:02d}')
        g=mapped_truth(row,meta);a=np.asarray(Image.open(LAB/'preflight'/f'case{row["case"]:02d}'/'input800.png').convert('RGB'),np.uint16)
        raw=((a.reshape(240,2,400,2,3).sum(axis=(1,3))+2)//4).astype(np.uint8)
        im=Image.fromarray(raw);draw=ImageDraw.Draw(im)
        for i,(_,x1,y1,x2,y2) in enumerate(g):
            draw.rectangle((float(x1),float(y1),float(x2),float(y2)),outline=(255,220,60),width=1)
            draw.text((float(x1),max(0,float(y1)-11)),f'G{i+1}',fill=(255,220,60))
        x=(at%2)*400;y=(at//2)*280;d.text((x+8,y+4),f"{row['case']:02d} {row['title']} / 数据集标注{len(g)}辆",font=font,fill=(230,240,250));canvas.paste(im,(x,y+32))
        preflight.append(dict(case=row['case'],ground_truth_cars=len(g),source_sha256=row['image_sha256'],source_meta=meta))
    canvas.save(PACK/'标注预览_非模型识别.png')
    write(LAB/'offline_preflight_verified.json',dict(status='ANNOTATION_GEOMETRY_AND_ONE_TO_ONE_MATCHING_PASS',
        cases=preflight,hardware_access=False,enhancement_computed=False,detections_computed=False))
    print('ROAD_OFFLINE_GEOMETRY_AND_MATCHING_PASS',len(rows),flush=True)

if __name__=='__main__':main()
