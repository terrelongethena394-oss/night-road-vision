from pathlib import Path
import json
root=Path('E:/FPGA_Enhance_Work/road_student_fusion_20261031_r1/board_candidate')
folders=sorted(root.glob('board_20261031_*'),key=lambda p:p.stat().st_mtime,reverse=True)
if folders:
    out=folders[0];print('EVIDENCE',out)
    for name in ['probe.log','start.log']:
        p=out/name
        if p.exists():print(name,p.read_text(encoding='utf-8',errors='replace')[-1800:])
    for p in sorted(out.glob('*/request.log')):
        print(p.parent.name,p.read_text(encoding='utf-8',errors='replace')[-800:])
for name in ['board_failed.json','board_verified.json','board_waiting.json']:
    p=root/name
    if p.exists():print(name,p.read_text(encoding='utf-8')[:2000])
