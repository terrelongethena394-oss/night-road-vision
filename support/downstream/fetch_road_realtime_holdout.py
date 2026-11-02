"""Freeze a new metadata-only holdout, excluding all previously observed groups/hashes."""
from pathlib import Path
import hashlib,importlib.util,json
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
BASE=Path('E:/FPGA_Enhance_Work/road_detection_20261026')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    previous=[BASE/'dataset/manifest.json',Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'),Path('E:/FPGA_Enhance_Work/road_light_20261027/fresh/manifest.json')]
    old=[r for p in previous for r in json.loads(p.read_text())];excluded={r['group'] for r in old};names={r['name'] for r in old};seed=2026102733
    paths={Path(x['rfilename']).name:x['rfilename'] for x in json.loads((BASE/'BDD100K_repo.json').read_text())['siblings'] if x['rfilename'].endswith('.jpg') and '/val/' in x['rfilename']}
    meta=[json.loads(line) for p in sorted((BASE/'source_metadata').glob('val_*.jsonl')) for line in p.read_text().splitlines()]
    selected=[];groups=set();quota={'night':240,'dawn/dusk':96,'daytime':144}
    for period,n in quota.items():
        pool=[r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in excluded]
        pool.sort(key=lambda r:hashlib.sha256((str(seed)+'|'+r['file_name']).encode()).hexdigest());count=0
        for r in pool:
            name=r['file_name'];group=name.split('-')[0]
            if group in groups:continue
            assert name not in names;selected.append(dict(name=name,group=group,timeofday=period,image_path=paths[name],split='fresh_test',official_split='val'));groups.add(group);count+=1
            if count==n:break
        assert count==n
    assert len(selected)==480 and not groups&excluded
    (ROOT/'fresh_selection.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
    protocol=dict(status='FROZEN_METADATA_ONLY_BEFORE_DOWNLOAD_AND_ANY_HOLDOUT_INFERENCE',seed=seed,quota=quota,selection='Hash order by name, one image per unseen first-prefix group; no prediction-based selection',excluded_manifest_sha256={str(p):sha(p) for p in previous},selected_names_sha256=sha(ROOT/'fresh_selection.json'),candidate_selection='Old validation epoch4/8 only; freeze selected checkpoint before reading new predictions',gates='NightAP>=.95*FP32 teacher; overallAP>=.97*teacher; person-night recall>=.90*teacher; nightFP<=1.1*teacher+2; personFP<=1.1*teacher+2. No tuning after reading this holdout.',same_source_limit='Same BDD100K source, not proof of cross-camera generalization',hardware_access=False,sd_written=False)
    (ROOT/'fresh_protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    code=(HERE/'fetch_road_light_holdout.py').read_text().replace('from road_light_common import ROOT,BASE,NAMES,read,write,sha','from road_light_common import BASE,NAMES,read,write,sha\nROOT=Path("E:/FPGA_Enhance_Work/road_realtime_20261027")')
    oldline="old=read(BASE/'dataset/manifest.json')+read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))"
    assert oldline in code;code=code.replace(oldline,oldline+"+read(Path('E:/FPGA_Enhance_Work/road_light_20261027/fresh/manifest.json'))")
    p=ROOT/'source/fetch_frozen_holdout_impl.py';p.write_text(code,encoding='utf-8');s=importlib.util.spec_from_file_location('fresh_impl',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.main()
    print('ROAD_REALTIME_NEW_HOLDOUT_480_READY_NO_MODEL_INFERENCE',flush=True)
if __name__=='__main__':main()
