from road_twilight_r2_common import ROOT,read,sha,write
from prove_road_twilight_native import prove
def main():
 fresh=read(ROOT/'fresh_complete.json');assert fresh['deployment_decision']!='retain_current'
 sel=read(ROOT/'selected.json');pipe=1 if fresh['deployment_decision']=='enhanced_input' else 2;choice=sel['candidate'] if pipe==1 else sel['control'];assert sha(choice['weights'])==choice['sha256']
 a=prove(ROOT,choice['weights'],2,'native_raw');b=prove(ROOT,choice['weights'],1,'native_enh');assert sha(a/'weights.f32')==sha(b/'weights.f32')
 for ca,cb in zip(read(a/'complete.json')['cases'],read(b/'complete.json')['cases']):assert ca['name']==cb['name'] and ca['input_sha256']==cb['input_sha256']
 write(ROOT/'native_complete.json',dict(status='BOTH_RAW_AND_ENHANCED_INPUTS_ALL8_ALL86_NATIVE_PROVEN',pipe_mode=pipe,chosen_checkpoint=choice,weights_sha256=sha(a/'weights.f32'),raw_proof_sha256=sha(a/'complete.json'),enh_proof_sha256=sha(b/'complete.json'),fresh_result_sha256=sha(ROOT/'fresh_complete.json'),hardware_access=False,sd_written=False))
if __name__=='__main__':main()
