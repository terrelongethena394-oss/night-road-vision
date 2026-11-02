"""Preserve raw logs and separate reused YOLO callback CSV appends from training runs."""
import csv,time
from pathlib import Path
from road_light_common import ROOT,VARIANTS,read,write,sha

def main():
    start=time.monotonic()
    while not (ROOT/'training_complete.json').exists():
        if time.monotonic()-start>7200:raise TimeoutError('Training incomplete')
        time.sleep(5)
    out=ROOT/'training_audit';out.mkdir(exist_ok=False);allrows={};receipts=[]
    for tag in VARIANTS:
        path=ROOT/'runs'/tag/'results.csv'
        with path.open() as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        allrows[tag]=rows;assert [int(float(r[fields[0]])) for r in rows[:40]]==list(range(40))
        target=out/(tag+'_own_40_epochs.csv')
        with target.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows[:40])
        receipts.append(dict(variant=tag,raw_csv_rows=len(rows),own_training_rows=40,own_rows_sha256=sha(target),raw_csv_sha256=sha(path),raw_preserved=True))
    a,b,c=[allrows[t] for t in VARIANTS];assert len(a)==120 and len(b)==80 and len(c)==40
    assert a[40:80]==b[:40] and a[80:120]==c[:40] and b[40:80]==c[:40]
    # Verify that actual model files are distinct architectures despite logging callbacks.
    import os,sys
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    import torch
    architecture=[]
    for tag in VARIANTS:
        receipt=read(ROOT/'frozen'/tag/'complete.json');proof=read(ROOT/'initialization'/tag/'proof.json')
        for name,digest in receipt['weights'].items():
            p=ROOT/'frozen'/tag/name;assert sha(p)==digest
            ckpt=torch.load(p,map_location='cpu',weights_only=False);m=ckpt.get('ema') or ckpt['model'];count=sum(p.numel() for p in m.parameters())
            assert count==proof['parameters'] and m.yaml['width_multiple']==VARIANTS[tag]
            architecture.append(dict(variant=tag,file=name,sha256=digest,parameters=count,width_multiple=m.yaml['width_multiple']))
    write(out/'complete.json',dict(status='TRAINING_WEIGHTS_DISTINCT_AND_40_OWN_EPOCHS_EXTRACTED_RAW_CSV_PRESERVED',receipts=receipts,architecture=architecture,
       csv_issue='Upstream train.main has a shared default Callbacks instance. Sequential train.run calls accumulate logging callbacks, so earlier run CSVs receive later run rows. First40rows per run are own epochs. Weights saved directly by the training core remain in their own run directories, confirmed architecture/hash.',
       effect='No claim based on concatenated CSV. Use own40 files; actual frozen weights evaluated independently. Future multi-run training must construct freshCallbacks per invocation.',
       no_new_training=True,no_hardware=True))
    print('LIGHT_TRAINING_AUDIT_COMPLETE',flush=True)
if __name__=='__main__':main()
