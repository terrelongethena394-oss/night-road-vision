"""Audit reused development sources and separation; no new image download."""
from pathlib import Path
import numpy as np
from road_enhanced_detection_common import BASE,read,write,sha
import road_accuracy_common as ac
from study_roi_enhancement_attribution_20261031 import ROOT,MODELS

def main():
    rows=read(ROOT/'development_manifest.json')
    base=read(BASE/'road_allview_enhance_20261031_r1/predictions.json')['raw']
    assert [r['name'] for r in rows]==[r['name'] for r in base]
    train=read(BASE/'road_enhanced_detection_20261031_r1/training_manifest.json')
    assert not {r['group'] for r in train}&{r['group'] for r in rows}
    fresh=read(BASE/'road_car_roi_delivery_20261031_r1/confirmation/fresh/manifest.json')
    assert not {r['group'] for r in fresh}&{r['group'] for r in rows}
    details=[];objects=0
    for r,b in zip(rows,base):
        p=Path(r['data_root'])/'images'/r['name'];label=p.parent.parent/'labels'/(p.stem+'.txt')
        digest=sha(p)
        if r.get('image_sha256'):assert r['image_sha256']==digest
        truth=ac.truth(label);truth=truth[truth[:,0]==1]
        cached=np.asarray(b['ground_truth'],np.float32).reshape(-1,5)
        assert np.array_equal(truth,cached)
        objects+=len(truth);details.append(dict(name=r['name'],group=r['group'],image_sha256=digest,label_sha256=sha(label)))
    write(ROOT/'source_audit.json',dict(status='ALL480_REUSED_DEV_SOURCES_AND_GROUND_TRUTH_AUDITED',images=len(rows),car_ground_truth=objects,
        no_training_prefix_group_overlap=True,no_prior304_confirmation_prefix_group_overlap=True,
        model_sha256={name:sha(p) for name,p in MODELS.items()},
        prior304_predictions_accessed=False,prior304_manifest_only_checked_for_separation=True,
        new_photographs_downloaded=False,hardware_access=False,sd_written=False,details=details))
    print('ROI_ATTRIBUTION_SOURCE_AUDIT_PASS',len(rows),objects,flush=True)

if __name__=='__main__':main()
