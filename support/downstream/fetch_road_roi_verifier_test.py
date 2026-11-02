"""New seal for the verifier, never reusing the previous geometry test outcomes."""
from pathlib import Path
import hashlib,importlib.util,json
from road_roi_verifier_common import *
HERE=Path(__file__).resolve().parent

def main():
 chosen=read(ROOT/'selected.json');assert chosen['qualified'];assert not (ROOT/'fresh_selection.json').exists()
 paths_old=[BASE/'dataset/manifest.json',BASE.parent/'road_joint_adapt_20261026/fresh/manifest.json',BASE.parent/'road_light_20261027/fresh/manifest.json',BASE.parent/'road_realtime_20261027/fresh/manifest.json',BASE.parent/'road_twilight_20261027/fresh/manifest.json',R2/'extra/manifest.json',GUARD/'fresh/manifest.json']
 old=[r for p in paths_old for r in read(p)];excluded={r['group'] for r in old};seed=2026102855;paths={Path(r['rfilename']).name:r['rfilename'] for r in read(BASE/'BDD100K_repo.json')['siblings'] if r['rfilename'].endswith('.jpg') and '/train/' in r['rfilename']}
 meta=[json.loads(s) for p in sorted((BASE/'source_metadata').glob('train_*.jsonl')) for s in p.read_text(encoding='utf-8').splitlines()];selected=[];used=set()
 for period,n in [('dawn/dusk',160),('night',192),('daytime',128)]:
  pool=[r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in excluded and int(hashlib.sha256(('2026102621|'+r['file_name'].split('-')[0]).encode()).hexdigest()[:8],16)%100>=85];pool.sort(key=lambda r:hashlib.sha256((str(seed)+'|'+r['file_name']).encode()).hexdigest());count=0
  for r in pool:
   group=r['file_name'].split('-')[0]
   if group in used:continue
   used.add(group);selected.append(dict(name=r['file_name'],group=group,timeofday=period,image_path=paths[r['file_name']],split='fresh_test',official_split='train_reserved_unseen'));count+=1
   if count==n:break
  assert count==n,(period,count,n)
 write(ROOT/'fresh_selection.json',selected)
 write(ROOT/'fresh_protocol.json',dict(status='VERIFIER_NEW480_FROZEN_BEFORE_DOWNLOAD_OR_FORWARD',seed=seed,selection_sha256=sha(ROOT/'fresh_selection.json'),chosen_sha256=sha(ROOT/'selected.json'),verifier_sha256=chosen['chosen']['sha256'],floor=chosen['chosen']['floor'],policy=read(ROOT/'protocol.json')['roi_policy'],excludes={str(p):sha(p) for p in paths_old},source='Unseen originalBDDtrain reserved groups, same source only. Excludes every previous test including current geometry480.',release='Same old quality gates and all three time FP/personFP<=1.10baseline+2. DuskAP pairedbootstrap97.5% lower>0 (1000,seed2026102856), conservative interval for second development-stage attempt. No model/floor changes after test.',hardware_access=False,sd_written=False))
 source=(HERE/'fetch_road_light_holdout.py').read_text(encoding='utf-8').replace('from road_light_common import ROOT,BASE,NAMES,read,write,sha','from road_roi_verifier_common import BASE,read,write,sha\nfrom road_adapt_common import NAMES\nROOT=Path('+repr(ROOT.as_posix())+')');oldline="old=read(BASE/'dataset/manifest.json')+read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))";assert source.count(oldline)==1;source=source.replace(oldline,'old='+ '+'.join('read(Path('+repr(p.as_posix())+'))' for p in paths_old))
 path=ROOT/'source/fetch_new_reserve_test.py';path.write_text(source,encoding='utf-8');spec=importlib.util.spec_from_file_location('verifier_new_fetch',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.main();print('VERIFIER_NEW_UNSEEN480_READY',flush=True)
if __name__=='__main__':main()
