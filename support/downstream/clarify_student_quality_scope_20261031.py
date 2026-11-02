"""Correct evaluation scope after resized-pixel provenance audit;keep originals."""
from pathlib import Path
import hashlib,json,collections
import numpy as np
from PIL import Image
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_student_fusion_20261031_r1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def pixelsha(p):return hashlib.sha256(np.asarray(Image.open(p).convert('RGB').resize((400,240),Image.Resampling.BILINEAR)).tobytes()).hexdigest()
def main():
    split=read(BASE/'model_upgrade_20261023/student_training_split.json');paired=BASE/'model_upgrade_20261023/dataset/our485';normal=BASE/'enhancement_study_20261025/data/Normal'
    fit={pixelsha(paired/'high'/n):n for n in split['train']};internal={pixelsha(paired/'high'/n):n for n in split['validation']}
    groups={p.name.replace('normal','low'):pixelsha(p) for p in normal.glob('*.png')}
    excluded={n:fit[g] for n,g in groups.items() if g in fit};assert len(excluded)==3
    rows=[r for r in read(ROOT/'complete.json')['paired_rows'] if r['name'] not in excluded]
    methods=['current','fusion'];perimage={m:{k:float(np.mean([r[k] for r in rows if r['method']==m])) for k in ['psnr','ssim']} for m in methods}
    groupavg={}
    for m in methods:
        rr=[r for r in rows if r['method']==m];gg=sorted({groups[r['name']] for r in rr});groupavg[m]={k:float(np.mean([np.mean([r[k] for r in rr if groups[r['name']]==g]) for g in gg])) for k in ['psnr','ssim']}
    result=dict(status='QUALITY_SCOPE_CORRECTION_RETAIN_ORIGINAL_RESULTS',
      finding='Three20diagnostic low-exposure variants share one resized-exact normal target with direct fit pair703.png. Whole-file hash did not detect differently encoded/resized duplicates. Earlier no-direct-diagnostic-training assumption was incomplete.',
      original20='Development/training-domain diagnostic only;not heldout or independent and not evidence of generalization. Original files/results/protocol are retained.',
      excluded_by_source_identity_not_metrics=excluded,remaining_images=len(rows)//2,remaining_reference_groups=len({groups[r['name']] for r in rows}),remaining_per_image=perimage,remaining_group_average=groupavg,
      internal_fit_resized_overlap=sorted(set(fit)&set(internal)),
      remaining_scope='Previously used development regression only. Exact pixel filtering does not rule out related scenes;pretrained teacher training may overlap source benchmark. No independent quality claim.',
      decision='Candidate remains a temporary display experiment with unchanged RAW detection;no detection accuracygain or independent image-qualitygain claim. Actual JTAG validation pending.',hardware_programmed=False,sd_written=False)
    write(ROOT/'quality_scope_correction.json',result)
    print('QUALITY_SCOPE_CORRECTED',json.dumps(result),flush=True)
if __name__=='__main__':main()
