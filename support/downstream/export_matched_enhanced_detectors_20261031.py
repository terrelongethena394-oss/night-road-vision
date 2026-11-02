import shutil
from road_enhanced_detection_common import *
from export_road_twilight_weights import pack
def main():
    selected=read(ROOT/'selected.json');assert selected['qualified'];assert not (ROOT/'export').exists()
    (ROOT/'export').mkdir();_,graph,original,shapes=pack(INITIAL)
    assert original.tobytes()==(INITIAL.parent/'weights.f32').read_bytes()
    for name,record in [('enhanced',selected['chosen']),('raw_control',selected['raw_control'])]:
        ck=Path(record['checkpoint']);assert sha(ck)==record['checkpoint_sha256'];_,candidate_graph,weights,ss=pack(ck)
        assert graph==candidate_graph and weights.shape==original.shape and (weights!=original).any()
        out=ROOT/'export'/name;out.mkdir();weights.tofile(out/'weights.f32');shutil.copy2(ck,out/'model.pt')
        write(out/'complete.json',dict(status='MATCHED_GLOBAL_EXPERT_EXPORTED',checkpoint_sha256=sha(ck),weights_sha256=sha(out/'weights.f32'),weight_floats=len(weights),changed_floats=int((weights!=original).sum()),graph_unchanged=True,shapes=ss,selection_sha256=sha(ROOT/'selected.json')))
    shutil.copy2(__file__,ROOT/'source'/Path(__file__).name);print('MATCHED_ENHANCED_EXPERTS_EXPORTED',flush=True)
if __name__=='__main__':main()
