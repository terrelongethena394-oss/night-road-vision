"""Export only a qualified development candidate to the existing board graph ABI."""
import shutil
from road_viewadapt_common import *

def main():
 selection_file=next(ROOT/n for n in ['selected_classcalibrated.json','selected_calibrated.json','selected.json'] if (ROOT/n).exists())
 selected=read(selection_file);assert selected['qualified'] and not (ROOT/'export').exists()
 ck=Path(selected['chosen']['checkpoint']);assert sha(ck)==selected['chosen']['sha256']
 from export_road_twilight_weights import pack
 baseline,graph,original,shapes=pack(WEIGHTS)
 assert original.tobytes()==(BASE/'road_arm_prototype_20261026/weights.f32').read_bytes(),'Exporter must reproduce accepted baseline before exporting new weights'
 model,newgraph,weights,shapes=pack(ck);assert graph==newgraph and weights.shape==original.shape and (weights!=original).any()
 out=ROOT/'export';out.mkdir();weights.tofile(out/'weights.f32');shutil.copy2(ck,out/'model.pt')
 write(out/'complete.json',dict(status='SELECTED_NEW_WEIGHTS_EXPORTED_TO_UNCHANGED_C_FPGA_ABI',source_checkpoint_sha256=sha(ck),weights_sha256=sha(out/'weights.f32'),graph_sha256=sha(BASE/'road_arm_prototype_20261026/graph.json'),baseline_export_byte_exact=True,weight_floats=len(weights),changed_floats=int((weights!=original).sum()),shapes=shapes,selection_file=str(selection_file),selection_sha256=sha(selection_file),postfusion_truck_bus_odds_gains=selected['chosen'].get('gains',[selected['chosen'].get('gain',1.)]*2),hardware_access=False,sd_written=False))
 print('VIEWADAPT_SELECTED_WEIGHTS_EXPORTED',sha(out/'weights.f32'),flush=True)

if __name__=='__main__':main()
