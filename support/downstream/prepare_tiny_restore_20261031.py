"""Train-only teacher targets; no evaluation labels or images in training."""
import shutil,time,hashlib
import numpy as np
import road_accuracy_common as ac
from road_tiny_restore_common import *
from road_retinex_project import illumination
from retinexformer_reference_runtime import Reference,ROOT as TEACHER

def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'frozen').mkdir()
    train=read(BASE/'road_enhanceadapt_20261030_r1/training_manifest.json')
    dev=read(BASE/'road_brightness_route_20261030_r1/fresh/manifest.json')
    rows=sorted([r for r in train if r['mean_raw']<=48],key=lambda r:hashlib.sha256((str(SEED)+r['name']).encode()).hexdigest())[:640]
    assert len(rows)==640
    assert not {r['group'] for r in rows}&{r['group'] for r in dev}
    assert not {r['image_sha256'] for r in rows}&{r['image_sha256'] for r in dev}
    for i,r in enumerate(rows):r['restore_split']='fit' if i<512 else 'internal_val'
    write(ROOT/'training_selection.json',rows)
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_TARGETS_GRADIENTS_AND_CANDIDATE_EVALUATION',seed=SEED,
      teacher='Original-author LOL_v1 Retinexformer; no GT mean; pretrained reference only.',teacher_manifest_sha256=sha(TEACHER/'weight_manifest.json'),
      training='640 hashed dark examples from original2400 annotated train sources only;512 fit/128 internal_val. Frozen raw detector and BN/anchors. No evaluation labels or photos for fitting.',
      architecture='Own411parameter residual restoration CNN:rawRGB+reflect101 mean3RGB+paper11x11 illumination (7channels),pointwise7to12 ReLU,depthwise3x3 zero-pad12 ReLU,pointwise12to12 ReLU,head12to3. Identity skip,localbrightness confidence y/(y+.02),highlight fade.65to.98. MeanY>48 exact bypass.',
      target='raw+sameconfidence/highlightgate*(teacher-raw),clip0to1. Gate also applied to model residual. Not authors model compressed byte-for-byte; own learned student.',
      optimization='Two branches from identical initialized weights:distill-only and joint.8epochs,batch8,AdamWlr.002cosine.0002,wd1e-5,clip5. L1teacher+.1gradientL1teacher; joint adds .5*(frozenYOLOComputeLoss/batch). Checkpoints4/8. No extra grid/epochs after development.',
      detector_sha256=sha(DETECTOR),
      development='Existing exposed80 development subset from predenoise screen; same one global view, frozen main model, fixed preprocess/thresholds. Does not represent full7view board accuracy.',
      detection_gates='low64 AP50>=raw+.005,P>=raw-.005,R>=raw+.005;bright16 exact bypass. Among passing candidates largest AP50. Candidate also inspected for visual damage. Pass requires new independent confirmation before accuracy claim.',
      quality_fallback='If no detection candidate passes, select lowest internal_val teacher L1 among4frozen models ONLY for display-restoration experiment. Detection stays unchanged RAW and no enhanced-detection gain claim. Require paired20 diagnostic improvement and visual review before temporary JTAG board trial.',
      fresh_policy='Never call exposed64/80/304/paired20 blind. New independent labels only after model/route frozen;exclude recorded prefix groups and exacthashes.',hardware_access=False,sd_written=False))
    for n in ['road_tiny_restore_common.py',Path(__file__).name,'road_retinex_project.py']:
        shutil.copy2(Path(__file__).with_name(n),ROOT/'source'/n)
    n=len(rows);raw=np.memmap(ROOT/'raw.u8',mode='w+',dtype='u1',shape=(n,240,400,3));target=np.memmap(ROOT/'target.u8',mode='w+',dtype='u1',shape=(n,240,400,3));illum=np.memmap(ROOT/'illum.f16',mode='w+',dtype='<f2',shape=(n,240,400))
    assert shutil.disk_usage(ROOT).free>1024**3
    ref=Reference();begin=time.monotonic()
    for i,r in enumerate(rows):
        p=BASE/'road_detection_20261026/dataset/images/train'/r['name'];assert sha(p)==r['image_sha256']
        _,a=ac.sensor400(p);z=ref.run(a);raw[i]=a;target[i]=z;illum[i]=illumination(a)
        if (i+1)%64==0:print('TINY_RESTORE_TEACHER',i+1,n,round(time.monotonic()-begin),flush=True)
    for a in [raw,target,illum]:a.flush()
    write(ROOT/'prepared.json',dict(status='TRAIN_ONLY_TEACHER_TARGETS_READY',images=n,fit=512,internal_val=128,
        files={name:sha(ROOT/name) for name in ['raw.u8','target.u8','illum.f16','training_selection.json']},seconds=time.monotonic()-begin,hardware_access=False,sd_written=False))
    print('TINY_RESTORE_DATA_READY',flush=True)
if __name__=='__main__':main()
