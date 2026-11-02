from pathlib import Path
from car_roi_delivery_common import BASE,ROOT,read
for path in [ROOT/'development_manifest.json',ROOT/'confirmation/fresh/manifest.json',ROOT/'confirmation/candidate_predictions.json']:
    data=read(path);print('SOURCE',path,flush=True)
    if isinstance(data,dict):print('KEYS',list(data),flush=True)
    else:
        print('ROWS',len(data),'KEYS',list(data[0]),flush=True)
        row={k:v for k,v in data[0].items() if k not in ('detections','ground_truth')}
        print(row,flush=True)
        if 'ground_truth' in data[0]:print('FIRST_GT',data[0]['ground_truth'][:2],flush=True)

if __name__=='__main__':pass
