"""Separate preregistered raw-detector fallback; never relabel enhancement failure."""
import sys,shutil
from road_enhanceadapt_common import *

def main():
 if '--register' in sys.argv:
  assert not (ROOT/'development_progress.json').exists() and not (ROOT/'secondary_protocol.json').exists()
  write(ROOT/'secondary_protocol.json',dict(status='REGISTERED_DURING_TRAINING_BEFORE_ANY_CANDIDATE_VALIDATION',
   relation='Secondary delivery fallback only. The primary enhancement hypothesis and failure remain unchanged.',
   selector='Use a primary-qualified enhanced-global candidate if one exists. Otherwise pick highest raw carAP among checkpoints passing secondary gates. Select exactly one candidate before any new holdout predictions.',
   gates=dict(raw_car_ap_gain_vs_initial=.005,precision_drop_max=.005,recall_drop_max=.005,fp_increase_max=0),
   route='MeanY<=48 uses selected new model with4RAW views; mean>48 exact current model with4RAW views. Enhancement remains display-only.',
   fresh='Same unused160 low+64 brighter, no test-driven replacement, carAP gain99% paired CI lower>0 versus initial. No enhancement-attribution claim for a raw fallback.',
   protocol_sha256=sha(ROOT/'protocol.json'),hardware_access=False,sd_written=False))
  print('SECONDARY_RAW_FALLBACK_REGISTERED_BEFORE_VALIDATION',flush=True);return
 primary=read(ROOT/'selected.json');assert (ROOT/'secondary_protocol.json').exists()
 if primary['qualified']:
  chosen=primary['chosen'];mode='enh'
 else:
  records=[]
  for record in primary['records']:
   b=record['initial_raw'];r=record['same_model_raw']
   gates=dict(ap_gain=r['ap50']>=b['ap50']+.005,precision=r['precision']>=b['precision']-.005,
              recall=r['recall']>=b['recall']-.005,false_positives=r['fp']<=b['fp'])
   records.append(dict(**record,secondary_gates=gates,secondary_passes=all(gates.values())))
  good=[r for r in records if r['secondary_passes']]
  chosen=max(good,key=lambda r:r['same_model_raw']['ap50']) if good else None;mode='raw'
  write(ROOT/'selected_detector_only.json',dict(qualified=bool(chosen),chosen=chosen,records=records,
   primary_enhancement_qualified=False,secondary_protocol_sha256=sha(ROOT/'secondary_protocol.json'),fresh_inference=False))
 result=dict(status='ONE_CANDIDATE_FROZEN_REQUIRES_UNUSED_CONFIRMATION' if chosen else 'NO_PRIMARY_OR_SECONDARY_CANDIDATE_KEEP_ABI27',
  qualified=chosen is not None,chosen=chosen,input_mode=mode if chosen else None,
  primary_enhancement_qualified=primary['qualified'],
  initial_checkpoint_sha256=sha(INITIAL),primary_selection_sha256=sha(ROOT/'selected.json'),
  secondary_protocol_sha256=sha(ROOT/'secondary_protocol.json'),fresh_inference=False,
  hardware_access=False,sd_written=False)
 write(ROOT/'delivery_selection.json',result)
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('ENHANCEADAPT_DELIVERY_SELECTION',result['qualified'],result['input_mode'],None if chosen is None else chosen['epoch'],flush=True)

if __name__=='__main__':main()
