"""New ARM plate-reader branch on the unchanged, verified enhancement bit."""
from pathlib import Path
import json,shutil,subprocess,struct,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from plate_common import ROOT,BASE,CHARS,sha,write
HERE=Path(__file__).resolve().parent
OLD=BASE/'multinex_camera_digit_upgrade_20261026'
OUT=BASE/'camera_plate_20261026'
PLATFORM=BASE/'multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain'
GCC=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe')
def main():
    global OUT
    guarded='guarded' in sys.argv;neon=guarded or 'neon' in sys.argv
    if guarded:OUT=BASE/'camera_plate_guarded_20261026'
    elif neon:OUT=BASE/'camera_plate_neon_20261026'
    result=json.loads((ROOT/'tiny_student01/test/results.json').read_text(encoding='utf-8'));assert result['accepted']
    native=ROOT/'tiny_student01/native';proof=json.loads((native/'complete.json').read_text(encoding='utf-8'))
    assert proof['status']=='PLATE_NATIVE_NUMPY_ALL_SCORES_EXACT'
    OUT.mkdir(exist_ok=True);assert not (OUT/'camera.elf').exists()
    src=OUT/'app_src';shutil.copytree(OLD/'app_src',src,ignore=shutil.ignore_patterns('cnn_weights.h','digit_arm_kernel.h','digit_camera_adapter.h'),dirs_exist_ok=True)
    for name,key in [('plate_weights.h','weights_header_sha256'),('plate_native_kernel.h','kernel_sha256')]:
        assert sha(native/name)==proof[key];shutil.copy2(native/name,src/name)
    if neon:shutil.copy2(HERE/'plate_arm_kernel.h',src/'plate_arm_kernel.h')
    (src/'digit_arm_kernel.h').write_text('#include "'+('plate_arm_kernel.h' if neon else 'plate_native_kernel.h')+'"\n',encoding='ascii')
    adapter=(HERE/'plate_camera_adapter.h').read_text().replace('@FRACTION@',str(proof['head_score_fraction']));(src/'digit_camera_adapter.h').write_text(adapter,encoding='ascii')
    main=(src/'main.c').read_text()
    needle='M_D_EVALS,M_D_ROIX,M_D_ROIY,M_D_ROISIZE,M_D_GRAY,M_D_SCORES,M_D_VERSION,M_D_SEQUENCE};'
    assert needle in main;main=main.replace(needle,needle[:-2]+',M_P_WIDTH,M_P_HEIGHT,M_P_TOKENS,M_P_SCORE_FRAC,M_P_NORMALIZED,M_P_FALLBACK,M_P_ORIGINAL_ALPHA};')
    main=main.replace('DIGIT_RECOGNITION?6U:','DIGIT_RECOGNITION?'+('8U:' if guarded else '7U:')).replace('Xil_DCacheFlushRange(0x04E00000U,8192U);','Xil_DCacheFlushRange(0x04E00000U,0x40000U);')
    old='''  if(!injected){mail[M_D_ROIX]=144;mail[M_D_ROIY]=64;mail[M_D_ROISIZE]=112;}
  if(mail[M_D_ROISIZE]<28 || mail[M_D_ROISIZE]>224 || mail[M_D_ROISIZE]%28U ||
     mail[M_D_ROIX]<1 || mail[M_D_ROIY]<1 || mail[M_D_ROIX]+mail[M_D_ROISIZE]>=WIDTH ||
     mail[M_D_ROIY]+mail[M_D_ROISIZE]>=HEIGHT)fatal(60);'''
    new='''  if(!injected){mail[M_D_ROIX]=8;mail[M_D_ROIY]=72;mail[M_D_ROISIZE]=384;mail[M_P_HEIGHT]=96;}
  if(mail[M_D_ROISIZE]<96 || mail[M_D_ROISIZE]>384 || mail[M_D_ROISIZE]%96U ||
     mail[M_P_HEIGHT]<32 || mail[M_P_HEIGHT]>192 || mail[M_P_HEIGHT]%32U ||
     mail[M_D_ROIX]<1 || mail[M_D_ROIY]<1 || mail[M_D_ROIX]+mail[M_D_ROISIZE]>=WIDTH ||
     mail[M_D_ROIY]+mail[M_P_HEIGHT]>=HEIGHT)fatal(60);'''
    assert old in main;main=main.replace(old,new);(src/'main.c').write_text(main,encoding='ascii')
    fontpath=ROOT/'NotoSansCJK-Regular.ttc';font=None;face=0
    for i in range(10):
        f=ImageFont.truetype(str(fontpath),20,index=i)
        if f.getname()[0]=='Noto Sans CJK SC':font=f;face=i;break
    assert font is not None,'Require Simplified Chinese font face'
    glyph=[];preview=Image.new('RGB',(17*30,4*36),'black')
    for i,char in enumerate(CHARS):
        mask=Image.new('L',(20,24));draw=ImageDraw.Draw(mask);b=font.getbbox(char);draw.text(((20-(b[2]-b[0]))//2-b[0],(24-(b[3]-b[1]))//2-b[1]),char,font=font,fill=255)
        a=(np.array(mask)>=96).astype(np.uint8);assert a.any()
        glyph.append([int(sum(int(a[y,x])<<(19-x) for x in range(20))) for y in range(24)])
        preview.paste(Image.fromarray(a*255).convert('RGB'),((i%17)*30,(i//17)*36))
    glyph=np.array(glyph,np.uint32);np.savez(OUT/'plate_glyphs.npz',glyphs=glyph,chars=np.array(CHARS));preview.save(OUT/'plate_glyph_preview.png')
    text='#ifndef PLATE_GLYPHS_H\n#define PLATE_GLYPHS_H\n#include <stdint.h>\nstatic const uint32_t PLATE_GLYPHS[68][24]={'+','.join('{'+','.join(map(str,r.tolist()))+'}' for r in glyph)+'};\n#endif\n'
    (src/'plate_glyphs.h').write_text(text,encoding='ascii');shutil.copy2(ROOT/'FONT_LICENSE.txt',OUT/'FONT_LICENSE.txt')
    write(OUT/'font_source.json',dict(path=str(fontpath),font_sha256=sha(fontpath),family=font.getname(),face=face,license='SIL Open Font License1.1',bitmap_header_sha256=sha(src/'plate_glyphs.h'),font_binary_not_redistributed=True))
    for name in ['camera.bit','camera.xsa','ps7_init.tcl','quality_policy.json','LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md','Xilinx.spec']:
        shutil.copy2(OLD/name,OUT/name)
    shutil.copy2(ROOT/'lprnet_source/LICENSE',OUT/'LPRNET_LICENSE.txt');shutil.copy2(ROOT/'tiny_student01/test/results.json',OUT/'plate_offline_results.json');shutil.copy2(ROOT/'tiny_student01/frozen_candidate.json',OUT/'plate_frozen.json');shutil.copy2(native/'complete.json',OUT/'plate_numeric_proof.json')
    shutil.copy2(ROOT/'tiny_student01/best_eligible.pth',OUT/'plate_model.pth');shutil.copy2(native/'integer_weights.npz',OUT/'plate_integer_weights.npz')
    flags=['-mcpu=cortex-a9','-mfpu='+('neon-vfpv3' if neon else 'vfpv3'),'-mfloat-abi=hard','-O2','-g','-fno-common','-Wall','-DUSE_DDR_CACHE=1','-DNORMAL_PROTECTION=1','-DDIGIT_RECOGNITION=1','-DPLATE_CONSISTENCY_GUARD='+str(int(guarded)),'-I'+str(PLATFORM/'bspinclude/include'),'-I'+str(src)]
    obj=OUT/'obj';obj.mkdir(exist_ok=True);objects=[];commands=[];logs=[]
    for p in sorted(src.rglob('*.c')):
        target=obj/('_'.join(p.relative_to(src).parts)+'.o');cmd=[str(GCC),*flags,*(['-Wextra','-Werror'] if p.name=='main.c' else []),'-c',str(p),'-o',str(target)]
        run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr)
        if run.returncode:(OUT/'build.log').write_text('\n'.join(logs));raise RuntimeError(logs[-1])
        objects.append(str(target))
    cmd=[str(GCC),*flags[:3],'-Wl,-build-id=none','-specs='+str(OUT/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-L'+str(PLATFORM/'bsplib/lib'),'-o',str(OUT/'camera.elf'),*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-Wl,--end-group']
    run=subprocess.run(cmd,capture_output=True,text=True);commands.append(cmd);logs.append(run.stdout+run.stderr);(OUT/'build.log').write_text('\n'.join(logs));assert run.returncode==0,logs[-1]
    elf=(OUT/'camera.elf').read_bytes();phoff=struct.unpack_from('<I',elf,28)[0];ent,num=struct.unpack_from('<HH',elf,42);regions=[]
    for i in range(num):
        kind,off,va,pa,sz,ms,fl,al=struct.unpack_from('<8I',elf,phoff+i*ent)
        if kind==1 and ms:assert 0x100000<=pa<pa+ms<=0x1000000;regions.append([pa,pa+ms])
    assert sha(OUT/'camera.bit')==sha(OLD/'camera.bit')
    for name in ['start_multinex_camera.tcl','run_checked.tcl','measure_multinex_camera.tcl']:shutil.copy2(HERE/name,OUT/name)
    write(OUT/'offline_camera.json',dict(status='PLATE_ARM_COMPILED_NOT_BOARD_VERIFIED',bit_sha256=sha(OUT/'camera.bit'),elf_sha256=sha(OUT/'camera.elf'),xsa_sha256=sha(OUT/'camera.xsa'),regions=regions,commands=commands,model_sha256=sha(OUT/'plate_model.pth'),recognition=True,normal_protection=True,mail_version=8 if guarded else 7,plate_contract=4 if guarded else 3,consistency_guard=guarded,default_roi=[8,72,384,96],gray=0x04e00000,scores=0x04e10000,tokens=0x04e20000,normalized=0x04e30000,classification_processor='ARM Cortex-A9 #0',enhancement_processor='PL unchanged r4d',arm_implementation='NEON pointwise/temporal, scalar remainder' if neon else 'Scalar',arm_optimized_header_sha256=sha(src/'plate_arm_kernel.h') if neon else None,sd_written=False,scope='Given rectangular plate ROI, seven-character blue plates. No automatic full-scene localization or eight-character green plates. No measured board speed yet.'))
    print('PLATE_ARM_COMPILED',len(elf),regions,flush=True)
if __name__=='__main__':main()
