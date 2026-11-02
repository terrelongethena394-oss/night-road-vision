"""Reuse frozen RAWdetail outputs;cache all potential smallbox corrections."""
import shutil,time
import numpy as np
from road_enhanced_detection_common import *
from evaluate_car_patch_verifier import cohorts
from study_balanced_car_20261030 import raw_helpers
from prove_balanced_car_c import RefinerC,locals_for
from evaluate_car_boxrefine import fuse_refined
from study_car_zoom_20261030 import map_zoom,XS
import road_accuracy_common as ac

def same_boxes(a,b,tol=.001):
    if a.shape!=b.shape:return False
    if not len(a):return True
    distances=np.max(np.abs(a[:,None,:]-b[None,:,:]),axis=2)
    # CPU/GPU near-tied confidence values may change sort order. Check a
    # one-to-one box correspondence, not unrelated row positions.
    candidates=distances<=tol;matched={}
    def assign(i,seen):
        for j in np.flatnonzero(candidates[i]):
            if int(j) in seen:continue
            seen.add(int(j))
            if int(j) not in matched or assign(matched[int(j)],seen):matched[int(j)]=i;return True
        return False
    return all(assign(int(i),set()) for i in np.argsort(candidates.sum(1),kind='stable'))

def main():
    assert not (ROOT/'helper_cache.json').exists();shutil.copy2(__file__,ROOT/'source'/Path(__file__).name)
    chosen=read(BASE/'road_car_balanced_20261030_r1/selected.json')['chosen']['source'];engine=RefinerC();result=[];begin=time.monotonic();calls=0
    for key,d in cohorts().items():
        helpers=raw_helpers(key,d);local=locals_for(key);reference={r['name']:r for r in read(BASE/'road_car_balanced_20261030_r1/c_proof'/f'{key}_predictions.json')}
        for at,r in enumerate(d['manifest']):
            name=r['name'];sensor,full=ac.sensor400(d['images']/name);h=helpers[name]
            base=ac.fuse(h[0],h[1:],.75);base=base[base[:,5]==1]
            original=np.asarray(d['base'][name]['detections'],np.float32).reshape(-1,6);original=original[original[:,5]==1]
            assert same_boxes(base,original),(key,name,base.shape,original.shape)
            # The accepted control is the original frozen reference, not a
            # reconstructed control with a different CPU/GPU tie ordering.
            base=original
            mapped=[map_zoom(local[name][j],x,152) for j,x in enumerate(XS)];outputs=[np.zeros((len(p),5),np.float32) for p in mapped]
            engine.begin(sensor)
            for j,pred in enumerate(mapped):
                for i,b in enumerate(pred):
                    if b[4]<.05:continue
                    image,meta=engine.crop(b);outputs[j][i]=engine.predict(image,meta);calls+=1
            engine.end();old=fuse_refined(base,mapped,outputs,chosen['strength'],chosen['cap'],chosen['class_gate'])
            expected=np.asarray(reference[name]['detections'],np.float32).reshape(-1,6)
            assert same_boxes(old,expected),(key,name,old.shape,expected.shape)
            result.append(dict(name=name,development_group=key,global_raw=h[0].tolist(),tiles_mapped=[p.tolist() for p in h[1:]],
                zoom_local=local[name],zoom_mapped=[p.tolist() for p in mapped],refiner_outputs=[p.tolist() for p in outputs],ground_truth=reference[name]['ground_truth'],baseline_accepted=reference[name]['detections']))
            if (at+1)%80==0:print('ENHANCED_DETAIL_HELPER_CACHE',key,at+1,len(d['manifest']),calls,round(time.monotonic()-begin),flush=True)
    write(ROOT/'helper_cache.json',result);write(ROOT/'helper_cache_proof.json',dict(status='FROZEN_RAW_HELPERS_REPRODUCE_ACCEPTED480',images=len(result),all_possible_refiner_calls=calls,
        source_selection_sha256=sha(BASE/'road_car_balanced_20261030_r1/selected.json'),cache_sha256=sha(ROOT/'helper_cache.json'),raw_helpers_unchanged=True,numerical_tolerance=.001,numerical_scope='Cached C helpers versus earlier GPU-derived base predictions have FP32 rounding differences;existing board/C tolerance. Accuracy gates unchanged;final candidate requires actual C confirmation.',hardware_access=False,sd_written=False))
    print('ENHANCED_RAW_HELPERS_READY',len(result),calls,flush=True)
if __name__=='__main__':main()
