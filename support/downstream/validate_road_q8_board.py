"""Validate later PHYSICAL Q8 readback. This script never connects to hardware."""
import sys,subprocess
from pathlib import Path
import numpy as np
from road_integer_common import ROOT,FLOAT,read,write,sha
from build_road_arm_probe import fnv
from verify_road_arm_host import compare_boxes

def validate(out,fixture):
    app=ROOT/'m125/arm_lcd_r1';config=read(app/'offline_complete.json');g=read(FLOAT/'graph.json');out=Path(out);host=ROOT/'m125/host'/fixture
    context=dict(x.split('=',1) for x in (out/'context.txt').read_text().splitlines() if '=' in x)
    assert context==dict(fixture=fixture,source='physical_q8_lcd_framebuffer_jtag_readback',elf_sha256=config['elf_sha256'],bit_sha256=config['bit_sha256'],weights_sha256=config['model_sha256'])
    assert sha(app/'road_lcd.elf')==config['elf_sha256'] and sha(app/'runtime/model.bin')==config['model_sha256']
    m=np.fromfile(out/'mailbox.bin','<u4');assert len(m)==39 and m[0]==0x524F4144 and m[1]==3 and m[2]==3 and m[6]==0 and m[4]==1
    raw=FLOAT/'cases'/fixture/'input400.u32';assert int(m[16])==fnv(raw.read_bytes()) and int(m[17])==config['weight_fnv32']
    assert m[15]<=300 and m[18]>0 and m[28]==1 and m[30]==0x7084 and m[31]<=1 and m[32]==0x02000000+int(m[31])*1152000 and m[35]==0 and m[38]==2
    assert (out/'input320.rgb').read_bytes()==(host/'input320.rgb').read_bytes()
    alltrace=(out/'trace.bin').read_bytes();assert len(alltrace)==int(m[14]);cursor=0;proof=[]
    for t in g['tensors']:
        i=t['id'];gold=(host/'trace'/f'{i:03d}.f32').read_bytes();a=alltrace[cursor:cursor+len(gold)];cursor+=len(gold);assert len(a)==len(gold)
        if i not in g['heads']:assert a==gold,(fixture,i,'integer feature mismatch');proof.append(dict(id=i,bytes_exact=True))
        else:
            aa=np.frombuffer(a,'<f4');bb=np.frombuffer(gold,'<f4');delta=abs(aa-bb);assert np.isfinite(aa).all() and np.all(delta<=2e-5+2e-6*abs(bb));proof.append(dict(id=i,max_abs=float(delta.max())))
    assert cursor==len(alltrace)
    for j,i in enumerate(g['heads']):
        a=np.fromfile(out/f'head{j}.f32','<f4');b=np.fromfile(host/'trace'/f'{i:03d}.f32','<f4');assert a.shape==b.shape and np.isfinite(a).all() and np.all(abs(a-b)<=2e-5+2e-6*abs(b))
    decoded=np.fromfile(out/'decoded.f32','<f4').reshape(-1,9);gold=np.fromfile(host/'decoded.f32','<f4').reshape(-1,9);assert decoded.shape==gold.shape and np.isfinite(decoded).all()
    delta=abs(decoded-gold);assert delta[:,:4].max()<=.004 and delta[:,4:].max()<=2e-5
    boxes={name:compare_boxes(np.fromfile(out/(name+'.f32'),'<f4').reshape(-1,6),np.fromfile(host/(name+'.f32'),'<f4').reshape(-1,6),.008) for name in ['boxes320','boxes400']}
    assert boxes['boxes400']['count']==m[15]
    def seconds(i):return (int(m[i])+int(m[i+1])*2**32)/int(m[18])
    ticks=int(m[19])+int(m[20])*2**32;hz=int(m[18]);ms=(ticks*1000+hz//2)//hz
    expected=out/'expected_frame.bgr';p=subprocess.run([str(app/'host/render.exe'),str(raw),str(out/'boxes400.f32'),str(expected),str(ms),str(int(m[36]))],capture_output=True,text=True,check=True);assert 'GUARDS_PASS' in p.stdout
    frame=(out/'frame.bgr').read_bytes();assert len(frame)==1152000 and fnv(frame)==int(m[37]) and frame==expected.read_bytes()
    regs=np.fromfile(out/'vdma_regs.bin','<u4');assert len(regs)==12 and regs[0]&1 and regs[1]&0xff0==0 and (regs[1]&1)==0 and ((int(regs[10])>>16)&0x1f)==int(m[31])
    result=dict(status='PHYSICAL_Q8_ARM_INTEGER_ALL86_TENSORS_DECODE_NMS_AND_LCD_FRAMEBUFFER_PASS',fixture=fixture,layers=proof,boxes=boxes,
       total_seconds=seconds(19),network_seconds=seconds(21),preprocess_seconds=seconds(23),postprocess_seconds=seconds(25),render_seconds=seconds(33),
       frame_sha256=sha(out/'frame.bgr'),elf_sha256=config['elf_sha256'],model_sha256=config['model_sha256'],camera_enabled=False,sd_written=False)
    write(out/'validated.json',result);return result
if __name__=='__main__':
    result=validate(Path(sys.argv[2]),sys.argv[1]);print('ROAD_Q8_PHYSICAL_ALL86_AND_FRAME_PASS',result['total_seconds'],flush=True)
