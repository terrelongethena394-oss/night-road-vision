"""Audit an existing older raw-only checkpoint on current inputs; validation only."""
from pathlib import Path
import cv2
from road_twilight_common import ROOT,BASE,read,write,sha
from evaluate_road_twilight import evaluate
def main():
 weights=Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/frozen/raw_control/best.pt');assert sha(weights)=='45bfb18bb7089ab455265a64930ea0a229498090e37285822df09ac8ab596dc3'
 out=ROOT/'prior_raw_audit';out.mkdir(exist_ok=True);assert not (out/'complete.json').exists();write(out/'protocol.json',dict(status='PRIOR_CHECKPOINT_AUDIT_FROZEN_BEFORE_FORWARD',weights_sha256=sha(weights),scope='Old validation320 only. Does not alter the current matched experiment rules. Possible initializer for a later separate experiment, not new-holdout model selection.',hardware_access=False))
 rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROOT/'dataset/manifest.json') if r['split']=='val'];results={}
 for mode in ['raw_control','enhance_adapt']:
  results[mode]=evaluate(weights,rows,lambda r,m=mode:cv2.imread(str(ROOT/'dataset'/m/'images/val'/(Path(r['name']).stem+'.png')))[:,:,::-1].copy(),out/mode,mode)
 write(out/'complete.json',dict(status='PRIOR_RAW_CHECKPOINT_CURRENT320_INPUTS_MEASURED',results=results,new_test_read=False,hardware_access=False));print('PRIOR_RAW_MODEL_AUDIT_COMPLETE',[(m,r['by_time']['dawn/dusk']['mAP50']) for m,r in results.items()],flush=True)
if __name__=='__main__':main()
