"""Static-image adaptive exposure runtime; CPU controls frozen PL networks."""
from pathlib import Path
import hashlib,json,shutil,struct,subprocess
import numpy as np
from PIL import Image
from train_real_digit_cnn import OUT
from prepare_fixed_image import BSP,TOOL

HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work/real_cnn_image_test_20261025')
ROOT=Path('E:/FPGA_Enhance_Work/real_cnn_adaptive_image_test_20261025')
FIXED=Path('E:/FPGA_Enhance_Work/fixed_image_test_20261025')

def main():
    ROOT.mkdir(exist_ok=True);assert not (ROOT/'runtime_prepared.json').exists()
    config=json.loads((OUT/'exposure_gate/gate_config.json').read_text())
    threshold=config['threshold'];assert 0<=threshold<=255
    for name in ('inputs','pc_roi_references'):(ROOT/name).mkdir(exist_ok=True)
    manifest=json.loads((BASE/'case_manifest.json').read_text(encoding='utf-8'));records=[]
    for c in manifest['cases']:
        c=dict(c);name=c['id']
        for ext in ('.png','.bgr888'):shutil.copy2(BASE/'inputs'/(name+ext),ROOT/'inputs'/(name+ext))
        rgb=np.array(Image.open(BASE/'inputs'/(name+'.png')).convert('RGB')).astype(np.int64)[112:336,480:704]
        gray=(77*rgb[:,:,0]+150*rgb[:,:,1]+29*rgb[:,:,2]+128)>>8
        mean=int((gray.sum()+25088)//50176);mode=int(mean<=threshold)
        c['roi_mean']=mean;c['expected_mode']=mode
        c['unconditional_enh_expected']=c['enh_expected'];c['unconditional_enh_margin']=c['enh_margin']
        if mode==0:
            c['enh_expected']=c['raw_expected'];c['enh_margin']=c['raw_margin']
            Image.fromarray(rgb.astype(np.uint8)).save(ROOT/'pc_roi_references'/(name+'_PC_ENH_ROI.png'))
        else:shutil.copy2(BASE/'pc_roi_references'/(name+'_PC_ENH_ROI.png'),ROOT/'pc_roi_references'/(name+'_PC_ENH_ROI.png'))
        c['file']=(ROOT/'inputs'/(name+'.bgr888')).as_posix();records.append(c)
    manifest['cases']=records;manifest['exposure_gate']=config
    (ROOT/'case_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['set image_cases [list \\']
    for r in records:
        parts=[]
        for k in ['id','file','truth','fnv','raw_expected','enh_expected','raw_margin','enh_margin','roi_mean','expected_mode']:parts.extend([k,'{'+str(r[k])+'}'])
        lines.append('    [dict create '+' '.join(parts)+'] \\')
    lines.append(']');(ROOT/'cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    shutil.copy2(BASE/'photo_sources_and_attribution.json',ROOT/'photo_sources_and_attribution.json')
    app=ROOT/'app_src';shutil.copytree(FIXED/'app_src',app,dirs_exist_ok=True)
    text=(HERE/'fixed_image_main.c').read_text(encoding='ascii')
    anchor='static u32 checksum(u32 address) {'
    helper='''static u32 roi_mean(u32 address) {
    volatile u8 *p=(volatile u8 *)address;
    u32 sum=0U,x,y;
    for(y=112U;y<336U;y++)for(x=480U;x<704U;x++) {
        u32 at=(y*800U+x)*3U;
        sum+=(77U*p[at+2U]+150U*p[at+1U]+29U*p[at]+128U)>>8;
    }
    return (sum+25088U)/50176U;
}
'''
    text=text.replace(anchor,helper+anchor)
    text=text.replace('u32 i,x,y,sequence,slot,start_frame,r,e,r2,attempt;',
        'u32 i,x,y,sequence,slot,start_frame,r,e,r2,attempt,mean,enhance_mode;')
    anchor='            mail[M_CHECKSUM]=checksum(FRAME_BASE+slot*FRAME_BYTES);'
    text=text.replace(anchor,anchor+f'''
            mean=roi_mean(FRAME_BASE+slot*FRAME_BYTES);
            enhance_mode=mean<={threshold}U?1U:0U;
            Xil_Out32(NN_BASE+0x20U,enhance_mode);
            mail[M_RESERVED]=mean|(enhance_mode<<8);
''')
    anchor='            mail[M_ENH_MARGIN]=read_word(ENH_BASE,DIGIT_REG_MARGIN);'
    text=text.replace(anchor,anchor+'''
            if(enhance_mode==0U && (mail[M_RAW]!=mail[M_ENH] || mail[M_RAW_MARGIN]!=mail[M_ENH_MARGIN])) {fail(10,sequence);continue;}
''')
    text=text.replace('IMAGE_TEST_READY no_camera no_s2mm','IMAGE_ADAPTIVE_READY no_camera no_s2mm')
    (app/'main.c').write_text(text,encoding='ascii')
    obj=ROOT/'obj';obj.mkdir(exist_ok=True);objects=[]
    common=['-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard']
    with (ROOT/'build_app.log').open('w',encoding='utf-8') as log:
        for src in app.rglob('*.c'):
            target=obj/(src.relative_to(app).as_posix().replace('/','_')+'.o')
            cmd=[str(TOOL/'arm-none-eabi-gcc.exe'),*common,'-Wall','-Wextra','-O2','-g','-c',
                '-I'+str(BSP/'bspinclude/include'),'-I'+str(app),str(src),'-o',str(target)]
            subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT);objects.append(str(target))
        cmd=[str(TOOL/'arm-none-eabi-gcc.exe'),*common,'-Wl,-build-id=none','-specs='+str(app/'Xilinx.spec'),
            '-Wl,-T,'+str(app/'lscript.ld'),'-L'+str(BSP/'bsplib/lib'),'-o',str(ROOT/'image_test.elf'),
            *objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-Wl,--end-group']
        subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
    elf=(ROOT/'image_test.elf').read_bytes();assert b'IMAGE_ADAPTIVE_READY' in elf
    entry,phoff=struct.unpack_from('<II',elf,24);phsize,phnum=struct.unpack_from('<HH',elf,42)
    regions=[]
    for i in range(phnum):
        kind,_,_,address,_,size,_,_=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if kind==1 and size:assert 0x100000<=address<address+size<0x02000000;regions.append([hex(address),hex(address+size)])
    (ROOT/'adaptive_app_build.json').write_text(json.dumps(dict(status='BUILT_NOT_DOWNLOADED',threshold=threshold,
        elf_sha256=hashlib.sha256(elf).hexdigest(),memory_regions=regions,entry=hex(entry),
        role='ARM integer ROI brightness statistics/mode control; enhancement and both classifiers remain PL hardware.',
        labels_or_expected_predictions_sent_to_board=False,sd_written=False),indent=2),encoding='utf-8')
    shutil.copy2(BASE/'start_fixed_image.tcl',ROOT/'start_fixed_image.tcl')
    run=(BASE/'run_fixed_image.tcl').read_text(encoding='ascii')
    run=run.replace('host_elapsed_ms"','host_elapsed_ms,roi_mean,enhance_mode"')
    anchor='    set dma [expr {[lindex $words 12]+0}]'
    run=run.replace(anchor,anchor+'''
    set metadata [expr {[lindex $words 16]+0}]
    set roi_mean [expr {$metadata&255}]
    set enhance_mode [expr {($metadata>>8)&1}]
    if {$roi_mean!=[dict get $entry roi_mean] || $enhance_mode!=[dict get $entry expected_mode]} {error "ARM exposure decision/reference mismatch"}
''')
    suffix='$dma,[expr {[clock milliseconds]-$t0}]"'
    assert suffix in run
    run=run.replace(suffix,'$dma,[expr {[clock milliseconds]-$t0}],$roi_mean,$enhance_mode"')
    (ROOT/'run_fixed_image.tcl').write_text(run,encoding='ascii')
    (ROOT/'runtime_prepared.json').write_text(json.dumps(dict(status='PREPARED_WAITING_FOR_ACCEPTED_SCORE64_BITSTREAM',threshold=threshold,sd_written=False),indent=2),encoding='utf-8')
    print('ADAPTIVE_IMAGE_RUNTIME_BUILT',threshold,len(records),flush=True)

if __name__=='__main__':main()
