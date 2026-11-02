"""Archive exact scripts and evidence; never packages a rejected model as a release."""
from pathlib import Path
import ast,shutil,zipfile
from road_twilight_r2_common import ROOT,read,write,sha
HERE=Path(__file__).resolve().parent

def main():
 assert (ROOT/'result_evidence.json').exists()
 review=ROOT/'review_source';review.mkdir(exist_ok=False)
 seeds=['road_twilight_common','road_twilight_r2_common','prepare_road_twilight','fetch_road_twilight_holdout','fetch_road_light_holdout','prepare_road_twilight_r2','train_road_twilight_r2','evaluate_road_twilight_r2','test_road_twilight_r2','export_road_twilight_weights','prove_road_twilight_r2_native','build_road_twilight_r2_app','validate_road_twilight_r2_board','run_road_twilight_r2_board','report_road_twilight_r2','archive_road_twilight_r2','export_road_arm','diagnose_road_twilight_r2','evaluate_road_center_roi','calibrate_road_center_roi','calibrate_road_center_roi_classwise','fetch_road_center_roi_test']
 todo=list(seeds);copied={}
 while todo:
  n=todo.pop();p=HERE/(n+'.py')
  if n in copied or not p.exists():continue
  shutil.copy2(p,review/p.name);copied[n]=sha(p)
  tree=ast.parse(p.read_text(encoding='utf-8-sig'))
  for node in ast.walk(tree):
   if isinstance(node,ast.Import):todo.extend(v.name.split('.')[0] for v in node.names)
   elif isinstance(node,ast.ImportFrom) and node.module:todo.append(node.module.split('.')[0])
 for n in ['road_fp32_host.c']:
  shutil.copy2(HERE/n,review/n)
 for n in ['LICENSE','requirements.txt']:shutil.copy2(ROOT/'yolov5'/n,review/('yolov5_'+n))
 write(review/'manifest.json',dict(status='EXACT_LOCAL_REVIEW_SOURCES',sources_sha256=copied,external_runtime='Python environment and YOLOv5 code remain in existing project paths. This archive is an evidence/source snapshot, not a standalone installer.',python_executable='E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe',pythonpath=['E:/FPGA_Enhance_Work/road_detector_lib','E:/FPGA_Enhance_Work/plate_gpu_lib']))
 files=[]
 for folder in ['review_source','source','runs','validation']:
  files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.c','.h','.md','.json','.txt'])
 # Predictions are included for independent AP/FP/recall recomputation, not just metrics.
 files.extend(p for p in (ROOT/'fresh_evaluation').rglob('*') if p.is_file() and p.suffix in ['.json','.npy'])
 files.extend(p for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.json','.md','.log'])
 files.extend([ROOT/'dataset/manifest.json',ROOT/'extra/manifest.json',ROOT/'fresh/manifest.json'])
 roi=ROOT.parent/'road_center_roi_20261027';roi_evidence=ROOT/'center_roi_evidence';roi_evidence.mkdir()
 for p in roi.rglob('*'):
  if p.is_file() and p.suffix=='.json':
   target=roi_evidence/p.relative_to(roi);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);files.append(target)
 for folder in [ROOT/'dataset/raw_control/labels',ROOT/'fresh/labels',ROOT/'extra/annotations',ROOT/'fresh/annotations']:
  files.extend(p for p in folder.rglob('*') if p.is_file())
 evidence=read(ROOT/'result_evidence.json');accepted=evidence['decision']!='retain_current'
 if accepted:
  choice=read(ROOT/'selected.json')['candidate' if evidence['decision']=='enhanced_input' else 'control']
  files.extend([Path(choice['weights']),Path(choice['weights']).with_name('frozen.json')])
  for folder in [ROOT/'firmware',ROOT/'native_raw/source',ROOT/'native_enh/source']:
   files.extend(p for p in folder.rglob('*') if p.is_file() and not any(v in p.relative_to(folder).parts for v in ['obj','board_fixed_r1']))
  files.extend(p for p in [ROOT/'native_raw/complete.json',ROOT/'native_enh/complete.json',ROOT/'firmware/board_fixed_r1/validated.json'] if p.exists())
 out=ROOT.parent/'road_twilight_consistency_20261027_evidence.zip';assert not out.exists()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in sorted(set(files)):
   assert p.exists(),p;z.write(p,'road_twilight_consistency_20261027/'+p.relative_to(ROOT).as_posix())
 write(ROOT/'archive_complete.json',dict(path=str(out),sha256=sha(out),bytes=out.stat().st_size,files=len(set(files)),accepted_model_included=accepted,board_running_receipt=evidence['board_running_receipt'],contains_raw_dataset_images=False,not_a_standalone_installer=True,sd_written=False))
 print('TWILIGHT_EVIDENCE_ARCHIVE_DONE',out,out.stat().st_size,flush=True)

if __name__=='__main__':main()
