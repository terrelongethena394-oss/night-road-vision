"""Meaningful host preparation/geometry checks, without any hardware access."""
from pathlib import Path
import tempfile
import numpy as np
from PIL import Image
from photo_station_core import prepare_photo,STAGING
from car_roi_delivery_common import write

def main():
    root=STAGING/'host_tests';root.mkdir(parents=True,exist_ok=True);results=[]
    for name,size,expected in [('landscape',(1600,900),([800,450],[0,15])),('portrait',(600,1000),([288,480],[256,0])),('native',(800,480),([800,480],[0,0]))]:
        p=root/(name+'_中文 空格.png');Image.new('RGB',size,(17,53,91)).save(p);dest=root/name;meta=prepare_photo(p,dest)
        assert meta['resized_size']==expected[0] and meta['padding_xy']==expected[1]
        a=np.frombuffer((dest/'source800.bgr').read_bytes(),np.uint8).reshape(480,800,3)
        x,y=meta['padding_xy'];w,h=meta['resized_size'];assert np.all(a[y:y+h,x:x+w]==[91,53,17])
        if y:assert np.all(a[:y]==0) and np.all(a[y+h:]==0)
        if x:assert np.all(a[:,:x]==0) and np.all(a[:,x+w:]==0)
        # Independently specified central source point maps through board400 and back.
        sx,sy=meta['scale_xy'];ox,oy=size[0]/2,size[1]/2
        bx,by=(ox*sx+x)/2,(oy*sy+y)/2
        assert abs((2*bx-x)/sx-ox)<1e-8 and abs((2*by-y)/sy-oy)<1e-8
        results.append(dict(case=name,passed=True))
    p=root/'rotated.jpg';im=Image.new('RGB',(80,40),(20,40,60));ex=Image.Exif();ex[274]=6;im.save(p,exif=ex);meta=prepare_photo(p,root/'rotated');assert meta['oriented_original_size']==[40,80]
    p=root/'transparent.png';Image.new('RGBA',(800,480),(255,0,0,0)).save(p);prepare_photo(p,root/'alpha');assert not any((root/'alpha/source800.bgr').read_bytes())
    write(root/'complete.json',dict(status='HOST_INPUT_AND_COORDINATE_MAPPING_CHECKS_PASS',cases=results,exif_orientation=True,alpha_black_composite=True,hardware_access=False))
    print('PHOTO_STATION_HOST_CHECKS_PASS',flush=True)

if __name__=='__main__':main()
