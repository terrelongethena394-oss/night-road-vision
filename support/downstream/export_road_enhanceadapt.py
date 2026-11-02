"""Export only the one fixed development candidate; preserve accepted binaries."""
import shutil
from road_enhanceadapt_common import *
from export_road_twilight_weights import pack

def main():
 selected=read(ROOT/'delivery_selection.json');assert selected['qualified']
 ck=Path(selected['chosen']['checkpoint']);assert sha(ck)==selected['chosen']['sha256']
 _,graph,original,shapes=pack(INITIAL)
 assert original.tobytes()==(INITIAL.parent/'weights.f32').read_bytes()
 _,candidate_graph,weights,shapes=pack(ck)
 assert graph==candidate_graph and original.shape==weights.shape and (weights!=original).any()
 out=ROOT/'export';out.mkdir();weights.tofile(out/'weights.f32');shutil.copy2(ck,out/'model.pt')
 write(out/'complete.json',dict(status='ONE_DEVELOPMENT_CANDIDATE_EXPORTED_UNCHANGED_GRAPH_REQUIRES_FRESH_TEST',
  source_checkpoint_sha256=sha(ck),weights_sha256=sha(out/'weights.f32'),
  input_mode=selected['input_mode'],selection_sha256=sha(ROOT/'delivery_selection.json'),
  graph_sha256=sha(BASE/'road_arm_prototype_20261026/graph.json'),weight_floats=len(weights),
  changed_floats=int((weights!=original).sum()),shapes=shapes,initial_export_byte_exact=True,
  hardware_access=False,sd_written=False))
 shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
 print('ENHANCEADAPT_EXPORTED',selected['input_mode'],sha(out/'weights.f32'),flush=True)

if __name__=='__main__':main()
