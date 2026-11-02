from pathlib import Path
import json
BASE=Path('E:/FPGA_Enhance_Work')
for name in ['road_enhanceadapt_20261030_r1/training_manifest.json','road_viewadapt_20261030_r1/training_manifest.json','road_brightness_route_20261030_r1/fresh/manifest.json','road_car_zoom_20261030_r1/confirmation/fresh/manifest.json']:
    a=json.loads((BASE/name).read_text(encoding='utf-8'));print('FILE',name,'LEN',len(a),'FIRST',json.dumps(a[0])[:4500])
print((BASE/'road_detection_20261026/road_hyp.yaml').read_text())
