"""Freeze selected student,compile portable C and verify identical data path."""
import os,ctypes as ct,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_retinex_student_common import *
from shadowlift_lab import words,unpack,mean_y,Baseline
from shadowlift_refine import final_display

def main():
    import torch
    selected=read(ROOT/'selected.json');folder=ROOT/'frozen'/selected['chosen'];meta=read(folder/'frozen.json')
    assert sha(folder/'model.pt')==meta['sha256'];assert not (ROOT/'c_proof').exists()
    out=ROOT/'c_proof';out.mkdir();(out/'source').mkdir();(out/'host').mkdir();(out/'known').mkdir()
    net=make_model().cuda().eval();state=torch.load(folder/'model.pt',map_location='cpu',weights_only=True);net.load_state_dict(state)
    keys=['first.weight','first.bias','depth.weight','depth.bias','point.weight','point.bias','head.weight','head.bias'];w=np.concatenate([state[k].numpy().reshape(-1) for k in keys]).astype('<f4');assert len(w)==411 and np.isfinite(w).all();w.tofile(out/'weights.f32')
    h='/* Own trained paper-residual student;selected using internal validation. */\n#ifndef ROAD_STUDENT_WEIGHTS_H\n#define ROAD_STUDENT_WEIGHTS_H\nstatic const float road_student_weights[411]={\n'+',\n'.join(','.join(float(v).hex()+'f' for v in w[i:i+6]) for i in range(0,len(w),6))+'\n};\n#endif\n'
    (out/'source/road_student_weights.h').write_text(h,encoding='ascii')
    old=BASE/'road_car_balanced_20261030_r1/board_candidate/firmware/source/road_retinex_c.h'
    (out/'source/road_retinex_c.h').write_text(old.read_text().replace('17U*ROAD_RETI_N','31U*ROAD_RETI_N'),encoding='ascii')
    shutil.copy2(Path(__file__).with_name('road_student_restore.c'),out/'source/road_student_restore.c')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH']
    cmd=[str(gcc),'-shared','-O2','-std=c99','-Wall','-Wextra','-Werror','-msse2','-mfpmath=sse','-ffp-contract=off','-I'+str(out/'source'),str(out/'source/road_student_restore.c'),'-lm','-o',str(out/'host/student.dll')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'build.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
    dll_path=os.add_dll_directory(str(gcc.parent));lib=ct.CDLL(str(out/'host/student.dll'))
    class Stats(ct.Structure):_fields_=[(n,ct.c_float) for n in ['mean_in','mean_out','noise_proxy','alpha','max_gain']]
    up=ct.POINTER(ct.c_uint32);fp=ct.POINTER(ct.c_float)
    lib.road_student_restore.argtypes=[up,up,ct.c_uint,fp,ct.POINTER(Stats),ct.c_void_p,ct.c_void_p]
    work=np.empty(31*96000+65536+4,np.float32);work.view(np.uint32)[-4:]=0x7fcabcde
    def run(a):
        raw=words(a).reshape(-1).copy();before=raw.copy();z=np.empty(96004,np.uint32);z[-4:]=0xdeadbeef;s=Stats()
        start=time.monotonic();err=lib.road_student_restore(raw.ctypes.data_as(up),z.ctypes.data_as(up),96000,work.ctypes.data_as(fp),ct.byref(s),None,None)
        assert err==0 and np.array_equal(raw,before) and np.all(z[-4:]==0xdeadbeef) and np.all(work.view(np.uint32)[-4:]==0x7fcabcde)
        return unpack(z[:96000]).reshape(240,400,3),time.monotonic()-start
    sources=read(BASE/'road_paper_recheck_20261031_r1/protocol.json')['sources'];tests=[];canvas=Image.new('RGB',(1600,840),(15,15,15));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);draw=ImageDraw.Draw(canvas)
    def prove(a,name):
        c,seconds=run(a);p=infer(net,a,torch);diff=np.abs(c.astype(np.int16)-p.astype(np.int16));maxdiff=int(diff.max());mean=float(diff.mean())
        assert maxdiff<=1 and mean<.005,(name,maxdiff,mean)
        tests.append(dict(name=name,max_abs=maxdiff,mean_abs=mean,c_seconds=seconds,input_unchanged=True,canaries_unchanged=True))
        return c
    for value in [0,1,4,16,47,48,49,128,255]:prove(np.full((240,400,3),value,np.uint8),'gray'+str(value))
    rng=np.random.default_rng(SEED);prove(rng.integers(0,40,(240,400,3),dtype=np.uint8),'dark_random')
    for i,s in enumerate(sources):
        a=unpack(np.fromfile(s['raw'],'<u4')).reshape(240,400,3);cur=unpack(np.fromfile(s['current'],'<u4')).reshape(240,400,3);z=prove(a,s['name'])
        Image.fromarray(z).save(out/'known'/f'{i}.png');words(z).tofile(out/'known'/f'{i}.u32')
        teacher=np.asarray(Image.open(BASE/f'retinexformer_reference_20261031_r1/evaluation/known_photos/{i}.png'))
        for col,(tag,img) in enumerate([('RAW',a),('CURRENT BOARD',cur),('PAPER RESIDUAL CNN (C)',z),('PC TEACHER ONLY',teacher)]):
            canvas.paste(Image.fromarray(img),(col*400,i*280+40));draw.text((col*400+4,i*280+4),s['name']+' '+tag,font=font,fill='white');draw.text((col*400+4,i*280+22),f'Mean Y {mean_y(img):.2f}',font=font,fill='white')
    canvas.save(out/'comparison.png')
    from study_road_local_enhance_v2 import resize400,rgb,metric
    paired=[];engine=Baseline()
    for path in sorted((BASE/'enhancement_study_20261025/data/Low').glob('*.png')):
        a=resize400(rgb(path));g=resize400(rgb(path.parent.parent/'Normal'/path.name.replace('low','normal')));z=prove(a,path.name);cur=final_display(a,engine.run(a))[0]
        for m,img in [('raw',a),('current',cur),('student_c',z)]:paired.append(dict(name=path.name,method=m,**metric(img,g)))
    summary={m:{k:float(np.mean([r[k] for r in paired if r['method']==m])) for k in ['psnr','ssim']} for m in ['raw','current','student_c']}
    quality=all(summary['student_c'][k]>summary['current'][k] for k in ['psnr','ssim'])
    write(out/'complete.json',dict(status='PORTABLE_C_STUDENT_VERIFIED',chosen=selected['chosen'],parameters=411,weights_sha256=sha(out/'weights.f32'),dll_sha256=sha(out/'host/student.dll'),
      c_torch_comparisons=tests,paired_diagnostic=summary,paired_rows=paired,quality_pass=quality,paired_not_blind=True,commands=[cmd],source_sha256={p.name:sha(p) for p in (out/'source').iterdir()},
      detection_route='Unchanged raw7views;no enhanced detection gain claim',hardware_access=False,sd_written=False))
    print('RETINEX_STUDENT_C_PROOF_READY','quality',quality,'paired',summary,'worst_pixel',max(r['max_abs'] for r in tests),flush=True)
if __name__=='__main__':main()
