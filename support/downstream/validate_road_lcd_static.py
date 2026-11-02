from pathlib import Path
import subprocess,sys,numpy as np
from PIL import Image
from road_arm_common import ROOT as NN,read,write,sha
from prepare_road_lcd_static import ROOT
from verify_road_arm_host import compare_boxes
from build_road_arm_probe import fnv
def main():
    fixture=sys.argv[1];out=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/('board_'+fixture)
    offline=read(ROOT/'offline_complete.json');tools=read(ROOT/'download_tools.json');g=read(NN/'graph.json');case=NN/'cases'/fixture
    context=dict(x.split('=',1) for x in (out/'context.txt').read_text().splitlines() if '=' in x)
    assert context==dict(fixture=fixture,source='physical_lcd_framebuffer_jtag_readback',elf_sha256=offline['elf_sha256'],bit_sha256=offline['bit_sha256'],weights_sha256=offline['weights_sha256'])
    m=np.fromfile(out/'mailbox.bin','<u4');assert len(m)==39 and m[0]==0x524F4144 and m[1]==2 and m[2]==3 and m[6]==0
    assert m[16]==tools['input_fnv'][fixture] and m[17]==read(NN/'arm_compile_complete_r2.json')['weight_fnv32'] and m[15]<=300
    assert m[30]==0x7084 and m[31]<=1 and m[32]==0x02000000+int(m[31])*1152000 and m[35]==0 and m[38]==2
    assert (out/'input320.rgb').read_bytes()==(case/'input320.rgb').read_bytes()
    heads=[]
    for j,i in enumerate(g['heads']):
        a=np.fromfile(out/f'head{j}.f32','<f4');b=np.fromfile(case/'golden'/f'{i:03d}.f32','<f4');assert a.shape==b.shape and np.isfinite(a).all()
        err=abs(a-b);assert np.all(err<=1e-4+1e-4*abs(b));heads.append(dict(head=j,max_abs=float(err.max())))
    a=np.fromfile(out/'decoded.f32','<f4').reshape(-1,9);b=np.fromfile(case/'decoded.f32','<f4').reshape(-1,9);delta=abs(a-b)
    assert np.isfinite(a).all() and delta[:,:4].max()<=.02 and delta[:,4:].max()<=2e-4
    boxes={}
    for name in ['boxes320','boxes400']:
        a=np.fromfile(out/(name+'.f32'),'<f4').reshape(-1,6);b=np.fromfile(case/(name+'.f32'),'<f4').reshape(-1,6);assert len(a)==m[15]
        boxes[name]=compare_boxes(a,b,.04 if name=='boxes400' else .03)
    ticks=int(m[19])+int(m[20])*2**32;hz=int(m[18]);ms=(ticks*1000+hz//2)//hz
    expected=out/'expected_frame.bgr';p=subprocess.run([str(ROOT/'host/render.exe'),str(case/'input400.u32'),str(out/'boxes400.f32'),str(expected),str(ms),str(int(m[36]))],capture_output=True,text=True,check=True)
    assert 'GUARDS_PASS' in p.stdout
    actual=(out/'frame.bgr').read_bytes();assert len(actual)==1152000 and fnv(actual)==int(m[37]) and actual==expected.read_bytes()
    regs=np.fromfile(out/'vdma_regs.bin','<u4');assert len(regs)==12 and regs[0]&1 and regs[1]&0xff0==0 and (regs[1]&1)==0
    assert ((int(regs[10])>>16)&0x1f)==int(m[31])
    Image.fromarray(np.frombuffer(actual,np.uint8).reshape(480,800,3)[:,:,::-1]).save(out/'actual_framebuffer.png')
    result=dict(status='PHYSICAL_ARM_DETECTION_AND_LCD_DMA_FRAMEBUFFER_ALL_BYTES_VERIFIED',fixture=fixture,boxes=boxes,heads=heads,
         frame_sha256=sha(out/'frame.bgr'),frame_fnv32=int(m[37]),render_matches_host_every_byte=True,lcd_id=int(m[30]),frame_slot=int(m[31]),dma_errors=0,
         inference_seconds=ticks/hz,render_and_present_seconds=(int(m[33])+int(m[34])*2**32)/hz,display_ms=ms,
         elf_sha256=offline['elf_sha256'],bit_sha256=offline['bit_sha256'],weights_sha256=offline['weights_sha256'],
         source='Actual framebuffer read from board; not a photograph of the physical panel',physical_panel_visually_confirmed=False,camera_enabled=False,sd_written=False)
    write(out/'validated.json',result);print('ROAD_LCD_PHYSICAL_NUMERIC_AND_FRAMEBUFFER_PASS',int(m[15]),'boxes',ticks/hz,'seconds',flush=True)
if __name__=='__main__':main()
