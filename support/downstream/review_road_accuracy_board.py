"""Match actual board boxes to labels; illustrative checks, not new AP testing."""
from road_accuracy_common import *
def main():
    proof=read(ROOT/'board_verified.json');cases={c['name']:c for c in read(ROOT/'firmware/cases.json')};records=[]
    for row in proof['results']:
        c=cases[row['name']];folder=Path(proof['evidence'])/'candidate23'/str(row['visit'])
        gt=truth(ROOT/'fresh/labels'/(Path(c['original_name']).stem+'.txt')) if c['name']!='control_black' else np.empty((0,5),np.float32)
        result={}
        for tag,file in [('baseline','baseline_boxes.f32'),('candidate','boxes.f32')]:
            p=np.fromfile(folder/file,'<f4').reshape(-1,6);ok=correct(p,gt,np.array([.5],np.float32))[0][:,0];car=p[:,5]==1
            result[tag]=dict(car_tp=int((car&ok).sum()),car_fp=int((car&~ok).sum()),all_classes_tp=int(ok.sum()),all_classes_fp=int((~ok).sum()))
        records.append(dict(name=c['name'],visit=row['visit'],results=result))
    default=next(r for r in records if r['name']==proof['final_photo'])
    assert default['results']['baseline']['car_tp']==1 and default['results']['candidate']['car_tp']==3
    assert default['results']['baseline']['car_fp']==default['results']['candidate']['car_fp']==0
    write(ROOT/'board_annotation_checks.json',dict(status='ACTUAL_BOARD_BOXES_MATCHED_TO_ORIGINAL_LABELS',scope='6 representative inputs plus revisit, not a new independent accuracy benchmark. Default success image chosen after offline testing for illustration.',confidence=.25,iou=.5,records=records))
    write(ROOT/'visual_review.json',dict(status='ACTUAL_FRAMEBUFFER_STATIC_DEMO_REVIEWED',reviewer='assistant',image=str(Path(proof['evidence'])/'candidate23/6/lcd_readback.png'),source_frame_sha256=sha(Path(proof['evidence'])/'candidate23/6/frame.bgr'),judgment='Original visible left with one car box, enhanced view right with three car boxes. Tree/road brighter; residual grain persists. Text and box positions agree with verified renderer.',physical_panel_manually_confirmed=False,accepted_for_fixed_photo_demo=True,sd_written=False))
    print('ACTUAL_BOARD_LABEL_CHECK_DEFAULT',default,flush=True)
if __name__=='__main__':main()
