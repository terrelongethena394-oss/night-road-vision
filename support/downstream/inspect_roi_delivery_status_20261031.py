from pathlib import Path
import json

root=Path('E:/FPGA_Enhance_Work/road_car_roi_delivery_20261031_r1')
for name in ['board_candidate/board_running.json','board_candidate/board_verified.json','board_candidate/board_failed.json','confirmation/fresh_result.json']:
    p=root/name
    if not p.exists():
        continue
    d=json.loads(p.read_text(encoding='utf-8'))
    print('\nFILE',name,'KEYS',list(d))
    if name.endswith('fresh_result.json'):
        for k,v in d.items():
            if k not in ['images','records','predictions','per_image','items']:
                s=json.dumps(v,ensure_ascii=False)
                print(k,s[:11000])
    else:
        for k,v in d.items():
            if k=='cases':
                print('cases', {n:{q:r.get(q) for q in ['status','processing_seconds','networks','rois','visible_cars']} for n,r in v.items()})
            else:
                print(k,str(v)[:2500])
    if 'evidence' in d and name.endswith('board_running.json'):
        evidence=Path(d['evidence'])
        for n in ['start.log',str(d.get('case',''))+'/request.log']:
            log=evidence/n
            if log.is_file():
                print('LOG_TAIL',n,log.read_text(encoding='utf-8',errors='replace')[-1800:])
