"""Freeze a previously unread reserve test after old-validation policy selection."""
from pathlib import Path
import hashlib,importlib.util,json
from road_roi_guard_common import ROOT,BASE,read,write,sha
HERE=Path(__file__).resolve().parent

def main():
 chosen=read(ROOT/'selected.json');assert chosen['qualified'];assert not (ROOT/'fresh_selection.json').exists()
 paths_old=[BASE/'dataset/manifest.json',BASE.parent/'road_joint_adapt_20261026/fresh/manifest.json',BASE.parent/'road_light_20261027/fresh/manifest.json',BASE.parent/'road_realtime_20261027/fresh/manifest.json',BASE.parent/'road_twilight_20261027/fresh/manifest.json',BASE.parent/'road_twilight_consistency_20261027/extra/manifest.json']
 old=[r for p in paths_old for r in read(p)];excluded={r['group'] for r in old};seed=2026102851
 paths={Path(r['rfilename']).name:r['rfilename'] for r in read(BASE/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/train/' in r['rfilename']}
 meta=[json.loads(s) for p in sorted((BASE/'source_metadata').glob('train_*.jsonl')) for s in p.read_text(encoding='utf-8').splitlines()];selected=[];used=set()
 for period,n in [('dawn/dusk',160),('night',192),('daytime',128)]:
  pool=[r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in excluded and int(hashlib.sha256(('2026102621|'+r['file_name'].split('-')[0]).encode()).hexdigest()[:8],16)%100>=85]
  pool.sort(key=lambda r:hashlib.sha256((str(seed)+'|'+r['file_name']).encode()).hexdigest());count=0
  for r in pool:
   group=r['file_name'].split('-')[0]
   if group in used:continue
   used.add(group);selected.append(dict(name=r['file_name'],group=group,timeofday=period,image_path=paths[r['file_name']],split='fresh_test',official_split='train_reserved_unseen'));count+=1
   if count==n:break
  assert count==n,(period,count,n)
 write(ROOT/'fresh_selection.json',selected)
 write(ROOT/'fresh_protocol.json',dict(status='GUARDED_ROI_NEW480_FROZEN_BEFORE_DOWNLOAD_OR_FORWARD',seed=seed,selection_sha256=sha(ROOT/'fresh_selection.json'),chosen_sha256=sha(ROOT/'selected.json'),policy=chosen['chosen']['policy'],excludes={str(p):sha(p) for p in paths_old},source='Previously unseen prefix groups from originalBDDtrain reserved hash bucket>=85. Not officialBDDvalidation; not a new camera source.',selection='Metadata hash order, one prefixgroup perimage. No quality/detection filtering.',release='All old quality gates, same point gates on new test, plus total and personFP in EACH time<=raw*1.10+2. Dusk mAP pairedbootstrap95% lower bound>0 (1000,seed2026102852). No automatic live replacement before actual latency/board validation.',hardware_access=False,sd_written=False))
 source=(HERE/'fetch_road_light_holdout.py').read_text(encoding='utf-8');source=source.replace('from road_light_common import ROOT,BASE,NAMES,read,write,sha','from road_roi_guard_common import ROOT,BASE,read,write,sha\nfrom road_adapt_common import NAMES')
 oldline="old=read(BASE/'dataset/manifest.json')+read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))";assert source.count(oldline)==1;source=source.replace(oldline,'old='+ '+'.join('read(Path('+repr(p.as_posix())+'))' for p in paths_old))
 folder=ROOT/'source';folder.mkdir(exist_ok=True);path=folder/'fetch_new_reserve_test.py';path.write_text(source,encoding='utf-8');spec=importlib.util.spec_from_file_location('guard_new_fetch',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.main();print('ROI_GUARD_NEW_UNSEEN480_READY',flush=True)
if __name__=='__main__':main()
