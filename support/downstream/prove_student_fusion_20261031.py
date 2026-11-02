"""Single fixed low-frequency fusion; actual portable C, unchanged RAW detector."""
import os,ctypes as ct,shutil,subprocess
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont
from road_retinex_student_common import ROOT as STUDY,BASE,read,write,sha
from shadowlift_lab import words,unpack,mean_y,Baseline,smooth
from shadowlift_refine import final_display
ROOT=BASE/'road_student_fusion_20261031_r1'

class Engine:
    def __init__(self):
        gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
        self.directory=os.add_dll_directory(str(gcc.parent));self.lib=ct.CDLL(str(ROOT/'host/fusion.dll'))
        class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
        self.Stats=Stats;self.up=ct.POINTER(ct.c_uint32);self.fp=ct.POINTER(ct.c_float)
        self.lib.road_retinex_c.argtypes=[self.up,self.up,ct.c_uint,self.fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
        self.work=np.empty(32*96000+65536+4,np.float32);self.work.view(np.uint32)[-4:]=0x7fcabcde
    def run(self,a):
        raw=words(a).reshape(-1).copy();before=raw.copy();out=np.empty(96004,np.uint32);out[-4:]=0xdeadbeef;s=self.Stats()
        assert self.lib.road_retinex_c(raw.ctypes.data_as(self.up),out.ctypes.data_as(self.up),96000,self.work.ctypes.data_as(self.fp),ct.byref(s),None,None)==0
        assert np.array_equal(raw,before) and np.all(out[-4:]==0xdeadbeef) and np.all(self.work.view(np.uint32)[-4:]==0x7fcabcde)
        return unpack(out[:96000]).reshape(240,400,3)

def main():
    assert not ROOT.exists();ROOT.mkdir();(ROOT/'source').mkdir();(ROOT/'host').mkdir();(ROOT/'known').mkdir()
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_FUSION_OUTPUTS',
      reason='Pure learned residual improved paired20 but made known-road sky/noise too bright;do not deploy pure student. Test one low-frequency correction retaining prior high-frequency texture/chroma.',
      method='Current ABI28classical enhancement first;frozen epoch32paper-residualCNN;D=Ystudent-Ycurrent;separable reflect101mean9x9;delta=.5*smoothD*rawhighlightfade.65,.98. Add identical delta toRGB,clamp delta to[-minRGB,254-maxRGB]. Currentmax>=245 unchanged. Wholeblack andrawmean>48 exactidentity.',
      selection='One fixed display-only candidate,no gain/kernel grid. Require paired20 diagnosticPSNR/SSIM above current,visualreview,scalarreference/Cproof before JTAG.',
      detection='Raw inputs,geometry,weights,refiner and PLbit unchanged. No enhancement-caused accuracygain claim.',
      prior_c_proof_sha256=sha(STUDY/'c_proof/complete.json'),hardware_access=False,sd_written=False))
    old=BASE/'road_car_balanced_20261030_r1/board_candidate/firmware/source';src=ROOT/'source'
    for name in ['road_retinex_c.c','road_shadowlift.c','road_shadowlift.h']:shutil.copy2(old/name,src/name)
    for name in ['road_student_restore.c','road_student_weights.h']:shutil.copy2(STUDY/'c_proof/source'/name,src/name)
    for name in ['road_student_fusion.c',Path(__file__).name]:shutil.copy2(Path(__file__).with_name(name),src/name)
    (src/'road_retinex_c.h').write_text((old/'road_retinex_c.h').read_text().replace('17U*ROAD_RETI_N','32U*ROAD_RETI_N'),encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-ffp-contract=off','-I'+str(src),*[str(src/n) for n in ['road_retinex_c.c','road_shadowlift.c','road_student_restore.c','road_student_fusion.c']],'-lm','-o',str(ROOT/'host/fusion.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(ROOT/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    engine=Engine();base_engine=Baseline();sources=read(BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources']
    # Independent simple array expression checks fusion of saved pure-C NN.
    tests=[];canvas=Image.new('RGB',(1200,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);d=ImageDraw.Draw(canvas)
    for i,s in enumerate(sources):
        a=unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3);cur=unpack(np.fromfile(s['current'],'<u4')).reshape(240,400,3);z=engine.run(a)
        nn=unpack(np.fromfile(STUDY/f'c_proof/known/{i}.u32','<u4')).reshape(240,400,3)
        base=final_display(a,base_engine.run(a))[0];yy=lambda q:(54*q[:,:,0].astype(np.float32)+183*q[:,:,1].astype(np.float32)+19*q[:,:,2].astype(np.float32))/256
        delta=cv2.blur(yy(nn)-yy(base),(9,9),borderType=cv2.BORDER_REFLECT_101)*.5*(1-smooth(.65,.98,a.max(2).astype(np.float32)/255))
        delta=np.clip(delta,-base.min(2).astype(np.float32),254-base.max(2).astype(np.float32));delta[base.max(2)>=245]=0
        py=np.floor(base.astype(np.float32)+delta[:,:,None]+.5).astype(np.uint8)
        diff=np.abs(py.astype(np.int16)-z.astype(np.int16));assert diff.max()<=2 and diff.mean()<.01,(i,diff.max(),diff.mean())
        tests.append(dict(name=s['name'],reference_max_abs=int(diff.max()),reference_mean_abs=float(diff.mean())))
        words(z).tofile(ROOT/'known'/f'{i}.u32');Image.fromarray(z).save(ROOT/'known'/f'{i}.png')
        for col,(tag,img) in enumerate([('RAW',a),('CURRENT BOARD',cur),('LEARNED EXPOSURE FUSION',z)]):
            canvas.paste(Image.fromarray(img),(col*400,i*280+40));d.text((col*400+5,i*280+5),s['name']+' '+tag,font=font,fill='white');d.text((col*400+5,i*280+22),f'MeanY {mean_y(img):.2f}',font=font,fill='white')
    canvas.save(ROOT/'comparison.png')
    for value in [0,49,128,255]:
        a=np.full((240,400,3),value,np.uint8);assert np.array_equal(a,engine.run(a))
    from study_road_local_enhance_v2 import resize400,rgb,metric
    paired=[]
    for path in sorted((BASE/'enhancement_study_20261025/data/Low').glob('*.png')):
        a=resize400(rgb(path));g=resize400(rgb(path.parent.parent/'Normal'/path.name.replace('low','normal')));z=engine.run(a);cur=final_display(a,base_engine.run(a))[0]
        for m,img in [('current',cur),('fusion',z)]:paired.append(dict(name=path.name,method=m,**metric(img,g)))
    summary={m:{k:float(np.mean([r[k] for r in paired if r['method']==m])) for k in ['psnr','ssim']} for m in ['current','fusion']}
    quality=all(summary['fusion'][k]>summary['current'][k] for k in ['psnr','ssim'])
    write(ROOT/'complete.json',dict(status='PORTABLE_C_DISPLAY_FUSION_VERIFIED_REQUIRES_VISUAL_REVIEW',quality_pass=quality,paired_summary=summary,paired_rows=paired,paired_not_blind=True,
      reference_tests=tests,commands=[cmd],dll_sha256=sha(ROOT/'host/fusion.dll'),source_sha256={p.name:sha(p) for p in src.iterdir()},
      raw_detection_unchanged=True,hardware_access=False,sd_written=False))
    print('STUDENT_FUSION_C_READY','quality',quality,'paired',summary,flush=True)

from pathlib import Path
if __name__=='__main__':main()
