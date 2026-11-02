"""Replay all previously captured board photos offline, then stage accepted model."""
from pathlib import Path
import json,shutil,sys
import numpy as np
from recognition_upgrade_common import ROOT,BASE,normalize_np,sha,write
from evaluate_recognition_upgrade import native
from validate_digit_camera import pooled
HERE=Path(__file__).resolve().parent
OLD=BASE/'multinex_camera_digit_fast_20261026'
BOARD=BASE/'multinex_camera_digit_upgrade_20261026'
def main():
    run=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'run02');out=run/'regression';out.mkdir(exist_ok=True)
    held=json.loads((run/'test/results.json').read_text());assert held['accepted'],'No deployment after heldout failure'
    freeze=json.loads((run/'frozen_candidate.json').read_text());assert held['model_sha256']==freeze['sha256']==sha(freeze['model'])
    cases=json.loads((OLD/'digit_cases.json').read_text(encoding='utf-8'));records=[];tensors=[]
    for c in cases:
        folder=OLD/'board_digit'/c['id'];x,y,size=c['roi']
        assert sha(folder/'input32.bin')==c['input_sha256']
        tensors.extend(pooled(np.fromfile(folder/n,np.uint8).reshape(240,400,4),x,y,size) for n in ['input32.bin','output32.bin','protected32.bin'])
    scores=native(run/'native/digit_arm_host.exe',normalize_np(np.stack(tensors)),out,'all_regression')
    for i,c in enumerate(cases):
        prev=json.loads((OLD/'board_digit'/c['id']/'digit_validation.json').read_text())
        new=scores[i*3:i*3+3].argmax(1).tolist()
        records.append(dict(id=c['id'],truth=c['truth'],scale=c['scale'],old_predictions=prev['predictions'],new_predictions=new))
    photos=[r for r in records if r['truth'] is not None]
    groups=[]
    for scale in [1.,.25,.125]:
        rs=[r for r in photos if r['scale']==scale]
        groups.append(dict(scale=scale,n=len(rs),old_correct=[sum(r['old_predictions'][i]==r['truth'] for r in rs) for i in range(3)],new_correct=[sum(r['new_predictions'][i]==r['truth'] for r in rs) for i in range(3)]))
    accepted=all(groups[0]['new_correct'][i]>=groups[0]['old_correct'][i] for i in [0,2])
    write(out/'results.json',dict(status='REGRESSION_NO_NORMAL_LIGHT_LOSS' if accepted else 'REGRESSION_LOSS_DO_NOT_DEPLOY',accepted=accepted,views=['RAW','NET','AUTO'],groups=groups,cases=records,limitation='Three previously seen Wikimedia source photos. Synthetic gain is not real night capture; not an independent generalization test. Pure enhancer unchanged; previously checked output buffers replayed, not new board results.'))
    assert accepted,'Normal-light regression loss; do not stage board'
    write(ROOT/'deployment_candidate.json',dict(native=str(run/'native'),freeze=str(run/'frozen_candidate.json'),heldout_results=str(run/'test/results.json'),regression=str(out/'results.json'),model_sha256=freeze['sha256'],sd_written=False))
    print('OFFLINE_REGRESSION_PASS',json.dumps(groups),flush=True)
    if len(sys.argv)>2 and sys.argv[2]=='stage':
        assert (BOARD/'camera.elf').exists()
        shutil.copytree(OLD/'digit_inputs',BOARD/'digit_inputs',dirs_exist_ok=True)
        lines=['set cases [list]']
        for c in cases:
            p=BOARD/'digit_inputs'/Path(c['file']).name;assert sha(p)==c['input_sha256'];c['file']=p.as_posix()
            x,y,size=c['roi'];lines.append(f'lappend cases [dict create id {c["id"]} file {{{c["file"]}}} fnv {c["input_fnv"]} x {x} y {y} size {size}]')
        write(BOARD/'digit_cases.json',cases);(BOARD/'digit_cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
        for n in ['test_digit_camera.tcl','snapshot_multinex_camera.tcl','measure_multinex_camera.tcl','validate_digit_camera.py']:
            shutil.copy2(HERE/n,BOARD/n)
        shutil.copy2(out/'results.json',BOARD/'classifier_regression.json')
        print('UPGRADE_BOARD_TESTS_STAGED',flush=True)
if __name__=='__main__':main()
