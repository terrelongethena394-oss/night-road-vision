from pathlib import Path
import json
p=Path('E:/FPGA_Enhance_Work/road_student_fusion_20261031_r1/board_candidate/firmware/arm_complete.json');d=json.loads(p.read_text())
print('REGIONS',[(n,hex(a),hex(s),hex(a+s)) for n,a,s in d['regions']])
print('LINK',[c for c in d['commands'] if '-c' not in c])
p=p.parent/'source/road_camera_draw.c';s=p.read_text();start=s.index('int road_camera_draw(');print(s[start:])
