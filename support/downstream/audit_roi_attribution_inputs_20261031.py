"""Check transform invariants without accessing new photographs or hardware."""
import numpy as np
from road_enhanced_detection_common import read,write,sha
from study_roi_enhancement_attribution_20261031 import ROOT,METHODS,enhance,mean_y
from prove_student_fusion_20261031 import Engine

def main():
    rng=np.random.default_rng(2026103198);engine=Engine();cases={
        'black':np.zeros((240,400,3),np.uint8),
        'bright':np.full((240,400,3),96,np.uint8),
        'dark_noise':rng.integers(0,32,(240,400,3),np.uint8),
        'dark_highlights':np.zeros((240,400,3),np.uint8)}
    cases['dark_highlights'][30:40,30:40]=255
    tests=[]
    for name,a in cases.items():
        before=a.copy();b=engine.run(a)
        for m in METHODS:
            c=enhance(a,m,b)
            assert c.shape==a.shape and c.dtype==np.uint8 and np.array_equal(a,before)
            if m=='raw' or mean_y(a)>48:assert np.array_equal(c,a)
            tests.append(dict(case=name,method=m,mean_in=mean_y(a),mean_out=mean_y(c),identity=bool(np.array_equal(c,a))))
    protocol=read(ROOT/'protocol.json')
    # Correct a textual arithmetic typo without changing frozen transformations or gates.
    write(ROOT/'method_count_clarification.json',dict(status='TEXT_ONLY_COUNT_CLARIFICATION',protocol_sha256=sha(ROOT/'protocol.json'),
          recorded_text=protocol['selection'],actual_routes=len(METHODS)*2,raw_routes=2,enhanced_routes=(len(METHODS)-1)*2,
          algorithms_changed=False,gates_changed=False,new_images_accessed=False,hardware_access=False))
    write(ROOT/'input_invariants.json',dict(status='SYNTHETIC_TRANSFORM_INVARIANTS_PASS',tests=tests,new_images_accessed=False,hardware_access=False,sd_written=False))
    print('ROI_ATTRIBUTION_SYNTHETIC_INVARIANTS_PASS',len(tests),flush=True)

if __name__=='__main__':main()
