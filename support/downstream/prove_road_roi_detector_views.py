"""Both real detail inputs through the unchanged original detector, all86 tensors."""
import cv2,numpy as np
from road_roi_spatial_common import ROOT,TEACHER,read,write,sha

def main():
 assert read(ROOT/'fresh_complete.json')['quality_accepted']
 from prove_road_twilight_native import prove
 import prepare_road_light
 full=prove(ROOT,TEACHER,2,'native_detector_full')
 def center(rgb):
  a=cv2.resize(rgb,(800,480),interpolation=cv2.INTER_LINEAR);a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248;return a[120:360,200:600].copy()
 previous=prepare_road_light.sensor_proxy
 try:
  prepare_road_light.sensor_proxy=center;roi=prove(ROOT,TEACHER,2,'native_detector_roi')
 finally:prepare_road_light.sensor_proxy=previous
 a=read(full/'complete.json');b=read(roi/'complete.json');assert a['weights_sha256']==b['weights_sha256'];assert [r['name'] for r in a['cases']]==[r['name'] for r in b['cases']]
 write(ROOT/'native_detector_complete.json',dict(status='BOTH_DETECTOR_VIEWS_ALL8_ALL86_NATIVE_C_PROVEN',weights_sha256=a['weights_sha256'],full_sha256=sha(full/'complete.json'),roi_sha256=sha(roi/'complete.json'),physical_fixture_selection='Use6 real camera-coherent cases plus black. Synthetic random is standalone operator proof only, not a coherent two-view sensor case.',hardware_access=False,sd_written=False));print('ROI_DETECTOR_BOTH_VIEWS_ALL86_PROVEN',flush=True)
if __name__=='__main__':main()
