"""Download preselected480 without any model inference or prediction-based filtering."""
from pathlib import Path
import importlib.util
from road_twilight_common import ROOT,BASE,read,write,sha,QUOTA
HERE=Path(__file__).resolve().parent
def main():
 assert (ROOT/'protocol.json').exists();selected=read(ROOT/'fresh_selection.json');assert len(selected)==480
 source=(HERE/'fetch_road_light_holdout.py').read_text(encoding='utf-8')
 source=source.replace('from road_light_common import ROOT,BASE,NAMES,read,write,sha','from road_twilight_common import ROOT,BASE,read,write,sha\nfrom road_adapt_common import NAMES')
 original="old=read(BASE/'dataset/manifest.json')+read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))";assert source.count(original)==1
 source=source.replace(original,original+"+read(Path('E:/FPGA_Enhance_Work/road_light_20261027/fresh/manifest.json'))+read(Path('E:/FPGA_Enhance_Work/road_realtime_20261027/fresh/manifest.json'))")
 p=ROOT/'source/fetch_frozen_holdout.py';p.write_text(source,encoding='utf-8');spec=importlib.util.spec_from_file_location('twilight_fetch',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.main()
 write(ROOT/'fresh_protocol.json',dict(status='FROZEN_SELECTION_FETCHED_WITHOUT_MODEL_INFERENCE',quota=QUOTA,source_sha256=sha(p),selection_sha256=sha(ROOT/'fresh_selection.json'),same_source_only=True,group_and_exact_hash_overlap=False,hardware_access=False,sd_written=False));print('TWILIGHT_NEW480_HOLDOUT_READY',flush=True)
if __name__=='__main__':main()
