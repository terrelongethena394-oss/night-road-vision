"""Development-only candidate search, frozen before independent evaluation."""
import time
from road_accuracy_common import *
from road_retinex_noiseguard import enhance

def development_rows():
    return [dict(name=r['name'],timeofday=r['timeofday'],image=str(DATA/'dataset/images/val'/r['name']),label=str(DATA/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))) for r in read(DATA/'dataset/manifest.json') if r['split']=='val' and r['status']=='READY']

def cache_views(rows,out,include_guard=True,requested=None):
    out.mkdir(parents=True,exist_ok=True);ev=Detector();predictions={}
    views=[('global',m,None) for m in ['raw','gamma080','gamma065']+(['guard22'] if include_guard else [])]
    views += [('tile',m,i) for m in GAMMAS for i in range(3)]
    if requested is not None:views=requested
    for kind,mode,index in views:
        tag=kind+'_'+mode+('' if index is None else '_'+str(index));file=out/(tag+'.json')
        if file.exists():predictions[tag]=read(file);continue
        result=[];begin=time.monotonic()
        for at in range(0,len(rows),16):
            rs=rows[at:at+16];images=[]
            for r in rs:
                sensor,full=sensor400(r['image'])
                im=full if kind=='global' else sensor[TILES[index][1]:TILES[index][1]+240,TILES[index][0]:TILES[index][0]+400]
                image=enhance(im,'guard_light')[0] if mode=='guard22' else gamma(im,mode)
                images.append(image)
            preds=ev.run(images)
            for r,p in zip(rs,preds):
                if kind=='tile':p=map_tile(p,*TILES[index]).tolist()
                result.append(dict(name=r['name'],timeofday=r['timeofday'],detections=p,ground_truth=truth(r['label']).tolist()))
            if (at+len(rs))%80==0:print('ACCURACY_DEV_VIEW',tag,at+len(rs),len(rows),round(time.monotonic()-begin,1),flush=True)
        write(file,result);predictions[tag]=result
        print('ACCURACY_VIEW_DONE',tag,round(time.monotonic()-begin,1),flush=True)
    del ev;return predictions

def make_fused(predictions,geometry,mode,weight):
    ids=[1] if geometry=='center' else [0,1,2]
    out=[]
    for at,r in enumerate(predictions['global_raw']):
        tiles=[predictions['tile_'+mode+'_'+str(i)][at]['detections'] for i in ids]
        pred=fuse(r['detections'],tiles,weight)
        original=np.asarray(r['detections'],np.float32).reshape(-1,6)
        assert np.array_equal(np.sort(pred[pred[:,5]==0],axis=0),np.sort(original[original[:,5]==0],axis=0))
        out.append(dict(name=r['name'],timeofday=r['timeofday'],ground_truth=r['ground_truth'],detections=pred.tolist()))
    return out

def summarize(m):
    n=m['by_time']['night'];c=n['classes']['car']
    return dict(night_car_ap50=c['ap50'],night_car_precision=c['precision'],night_car_recall=c['recall'],night_vehicle_ap50=n['vehicle_mAP50'],night_map50=n['mAP50'],all_map50=m['all']['mAP50'])

def main():
    assert (ROOT/'protocol.json').exists() and not (ROOT/'selected.json').exists()
    out=ROOT/'development';out.mkdir(exist_ok=True)
    rows=development_rows();assert len(rows)==320
    predictions=cache_views(rows,out/'views');scores={};records=[]
    for mode in ['raw','gamma080','gamma065','guard22']:
        tag='global_'+mode;m=metrics(predictions[tag]);scores[tag]=m;write(out/(tag+'_metrics.json'),m)
        records.append(dict(tag=tag,geometry='global',mode=mode,weight=None,passes=1,metrics=m))
        print('ACCURACY_SCORE',tag,summarize(m),flush=True)
    for geometry in ['center','three']:
        for mode in GAMMAS:
            for weight in [.3,.45,.6,.75]:
                tag=f'{geometry}_{mode}_w{int(weight*100)}';rr=make_fused(predictions,geometry,mode,weight);m=metrics(rr);scores[tag]=m
                records.append(dict(tag=tag,geometry=geometry,mode=mode,weight=weight,passes=2 if geometry=='center' else 4,metrics=m))
                write(out/(tag+'_metrics.json'),m);print('ACCURACY_SCORE',tag,summarize(m),flush=True)
    baseline=scores['global_raw'];bn=baseline['by_time']['night']['classes']['car'];qualified=[]
    for r in records:
        m=r['metrics'];cn=m['by_time']['night']['classes']['car']
        r['gates']=dict(night_car_ap=cn['ap50']>=bn['ap50']+.01,overall=m['all']['mAP50']>=baseline['all']['mAP50']-.005,night=m['by_time']['night']['mAP50']>=baseline['by_time']['night']['mAP50']-.005,car_precision=cn['precision']>=bn['precision']-.01,car_recall=cn['recall']>=bn['recall'],day_car=m['by_time']['daytime']['classes']['car']['ap50']>=baseline['by_time']['daytime']['classes']['car']['ap50']-.01)
        if all(r['gates'].values()):qualified.append(r)
    if qualified:
        best=max(r['metrics']['by_time']['night']['classes']['car']['ap50'] for r in qualified)
        near=[r for r in qualified if r['metrics']['by_time']['night']['classes']['car']['ap50']>=best-.005]
        chosen=min(near,key=lambda r:(r['passes'],-r['metrics']['by_time']['night']['classes']['car']['ap50']))
    else:chosen=records[0]
    # Freeze exactly one candidate; additional declared controls are attribution
    # only and cannot become a replacement after looking at the fresh set.
    result=dict(status='CANDIDATE_FROZEN_BEFORE_FRESH_INFERENCE',chosen=chosen,qualified=bool(qualified),records=records,protocol_sha256=sha(ROOT/'protocol.json'),weights_sha256=sha(WEIGHTS),no_fresh_inference=True)
    write(ROOT/'selected.json',result)
    print('ACCURACY_SELECTED',chosen['tag'],summarize(chosen['metrics']),chosen['gates'],flush=True)

if __name__=='__main__':main()
