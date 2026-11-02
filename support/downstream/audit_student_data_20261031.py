from pathlib import Path
import hashlib,json,shutil
import numpy as np
from PIL import Image
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_student_fusion_20261031_r1';BOARD=ROOT/'board_candidate'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    split=json.loads((BASE/'model_upgrade_20261023/student_training_split.json').read_text(encoding='utf-8'))
    old=BASE/'model_upgrade_20261023/dataset/our485'
    fit={sha(old/'high'/n):n for n in split['train']};internal={sha(old/'high'/n):n for n in split['validation']}
    targets=list((BASE/'enhancement_study_20261025/data/Normal').glob('*.png'))
    exact=[];pixel=[]
    resized={n:np.asarray(Image.open(old/'high'/n).convert('RGB').resize((400,240),Image.Resampling.BILINEAR)) for n in split['train']}
    hashes={hashlib.sha256(a.tobytes()).hexdigest():n for n,a in resized.items()}
    for p in targets:
        h=sha(p)
        if h in fit:exact.append([str(p),fit[h]])
        a=np.asarray(Image.open(p).convert('RGB').resize((400,240),Image.Resampling.BILINEAR));ph=hashlib.sha256(a.tobytes()).hexdigest()
        if ph in hashes:pixel.append([str(p),hashes[ph]])
    result=dict(status='EXACT_FILE_AND_RESIZED_PIXEL_OVERLAP_AUDIT',paired_fit=96,paired_internal=12,
        diagnostic_reference_files=len(targets),unique_diagnostic_file_hashes=len({sha(p) for p in targets}),
        fit_internal_normal_hash_overlap=list(set(fit)&set(internal)),fit_diagnostic_normal_file_overlap=exact,fit_diagnostic_resized_pixel_overlap=pixel,
        limits='Exact file/pixel checks do not prove distinct physical scenes;20paired diagnostic remains exposed/nonblind.',hardware_access=False,sd_written=False)
    (ROOT/'data_overlap_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    licenses=BOARD/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(BASE/'road_detection_20261026/yolov5/LICENSE',licenses/'YOLOv5_GPL-3.0.txt')
    shutil.copy2(BASE/'retinexformer_reference_20261031_r1/source/LICENSE.txt',licenses/'Retinexformer_MIT.txt')
    print('STUDENT_DATA_AUDIT',json.dumps(result),flush=True)
if __name__=='__main__':main()
