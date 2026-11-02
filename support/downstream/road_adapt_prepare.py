"""Build only train/validation paired views; reserve unseen source groups first."""
from pathlib import Path
import collections,concurrent.futures as cf,hashlib,json,shutil,subprocess,time
import cv2,numpy as np
from road_adapt_common import BASE,ROOT,REF,REF_SHA,SEED,NAMES,POLICIES,TRAIN_MILD,sha,read,write,canonical,apply_policy,frame_path

def main():
    ROOT.mkdir(exist_ok=False)
    assert sha(REF)==REF_SHA
    old=read(BASE/'dataset/manifest.json');old_groups={r['group'] for r in old};old_names={r['name'] for r in old}
    metadata=[]
    for p in sorted((BASE/'source_metadata').glob('val_*.jsonl')):
        metadata.extend(json.loads(s) for s in p.read_text().splitlines())
    repo=read(BASE/'BDD100K_repo.json');paths={Path(x['rfilename']).name:x['rfilename'] for x in repo['siblings'] if x['rfilename'].endswith('.jpg') and '/val/' in x['rfilename']}
    fresh=[];groups=set()
    for period,n in [('night',240),('dawn/dusk',96),('daytime',144)]:
        pool=[r for r in metadata if r['label']==period and r['file_name'].split('-')[0] not in old_groups and r['file_name'] in paths]
        pool.sort(key=lambda r:hashlib.sha256((str(SEED)+'|'+r['file_name']).encode()).hexdigest())
        count=0
        for r in pool:
            name=r['file_name'];group=name.split('-')[0]
            if group in groups:continue
            assert name not in old_names
            fresh.append(dict(name=name,group=group,timeofday=period,image_path=paths[name],official_split='val',split='fresh_test'));groups.add(group);count+=1
            if count==n:break
        assert count==n,(period,count,n)
    write(ROOT/'fresh_selection.json',fresh)
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_ADAPTATION_TRAINING_OR_NEW_TEST_INFERENCE',seed=SEED,
          initialization=str(BASE/'frozen/road4_best.pt'),initialization_sha256=sha(BASE/'frozen/road4_best.pt'),
          classes=NAMES,train_images=2400,val_images=320,fresh_test=len(fresh),fresh_test_periods=dict(collections.Counter(r['timeofday'] for r in fresh)),
          split_rule='New official-val groups exclude all3200 previous train/val/test filename prefixes, and each new test prefix appears once. Exact byte duplicates checked after download.',
          comparison='Two candidates, same first-round weights/seed/12epochs/batch16/optimizer/augmentation. raw_control sees canonical raw only; mixed sees raw50%, bounded30%, full_net20%. Same random draw consumed per load in both.',
          candidate_selection='Each run upstream raw-validation fitness only. Then choose candidate/policy by validation night mAP50, requiring raw all-map50 no more than1pp below raw_control and raw night-person recall no more than2pp below raw_control.',
          enhancement_acceptance='Selected nonraw policy needs validation night mAP50 >= same-detector raw+.005, person recall not >.02 lower, and total night FP no more than1.10*rawFP+2. Otherwise record failure; no invented gain.',
          policies=POLICIES,train_mild=TRAIN_MILD,previous480='Regression only after previous feedback. Not a new blind test.',
          detector_weights_trainable=True,enhancement_network_weights_trainable=False,board_modified=False,sd_written=False))
    source=ROOT/'yolov5';shutil.copytree(BASE/'yolov5',source,ignore=shutil.ignore_patterns('__pycache__','runs','*.pyc','*.pt'))
    for split in ['train','val']:
        for kind in ['raw','net','mild']:(ROOT/'frames'/split/kind).mkdir(parents=True)
        (ROOT/'frames'/split/'labels').mkdir()
        # YOLO label discovery replaces /images/ with /labels/, so expose canonical raw as images/{split}.
        (ROOT/'dataset/images'/split).mkdir(parents=True);(ROOT/'dataset/labels'/split).mkdir(parents=True)
    temp=ROOT/'reference_inputs';temp.mkdir()
    rows=[r for r in old if r['split'] in ['train','val'] and r['status']=='READY']
    def one(r):
        split,name=r['split'],r['name'];original=cv2.imread(str(BASE/'dataset/images'/split/name));assert original is not None
        raw=canonical(original[:,:,::-1]);stem=Path(name).stem;ip=temp/(split+'_'+stem+'.rgb');op=temp/(split+'_'+stem+'.net.rgb');ip.write_bytes(raw.tobytes())
        p=subprocess.run([str(REF),str(ip),'240','400',str(op)],capture_output=True,text=True)
        assert p.returncode==0 and 'MULTINEX_CPP_DONE' in p.stdout,p.stderr
        net=np.fromfile(op,np.uint8).reshape(240,400,3);mild=apply_policy(raw,net,TRAIN_MILD)
        for kind,a in [('raw',raw),('net',net),('mild',mild)]:assert cv2.imwrite(str(frame_path(split,kind,name)),a[:,:,::-1])
        dest=ROOT/'dataset/images'/split/(stem+'.png');shutil.copy2(frame_path(split,'raw',name),dest)
        label=BASE/'dataset/labels'/split/(stem+'.txt');shutil.copy2(label,ROOT/'dataset/labels'/split/label.name)
        return {**r,'raw_sha256':sha(dest),'net_sha256':sha(frame_path(split,'net',name)),'mild_sha256':sha(frame_path(split,'mild',name))}
    out=[];t=time.monotonic()
    with cf.ThreadPoolExecutor(4) as pool:
        for r in pool.map(one,rows):
            out.append(r)
            if len(out)%200==0:print('PAIRED_REAL_ROAD_VIEWS_READY',len(out),len(rows),flush=True)
    write(ROOT/'paired_manifest.json',out)
    yaml='path: '+(ROOT/'dataset').as_posix()+'\ntrain: images/train\nval: images/val\nnc: 4\nnames: [person, car, truck, bus]\n'
    (ROOT/'dataset/road4.yaml').write_text(yaml,encoding='ascii')
    write(ROOT/'prepare_complete.json',dict(status='TRAIN_VALIDATION_PAIRED_VIEWS_READY',train=2400,val=320,seconds=time.monotonic()-t,manifest_sha256=sha(ROOT/'paired_manifest.json'),fresh_selection_sha256=sha(ROOT/'fresh_selection.json')))
    print('PAIRED_TRAIN_VALIDATION_COMPLETE',time.monotonic()-t,flush=True)
if __name__=='__main__':main()
