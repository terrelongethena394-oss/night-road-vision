"""Serial physical A/B workflow with positive markers and numerical gates."""
from pathlib import Path
import os,sys,subprocess,time,runpy,struct
from road_integer_common import read,write,sha,FLOAT
from prepare_road_board_ab import ROOT,Q,FP
HERE=Path(__file__).resolve().parent
XSCT=Path('E:/Xilinx/Vitis/2020.2/bin/xsct.bat')

def xsct(script,args,log,marker):
    assert not log.exists()
    with log.open('w') as f:p=subprocess.run([str(XSCT),str(script),*map(str,args)],stdout=f,stderr=subprocess.STDOUT)
    text=log.read_text(errors='replace')
    assert marker in text and 'ROAD_AB_BATCH_FAILED' not in text and 'ROAD_LCD_FAILED:' not in text,(str(log),p.returncode,text[-3000:])
    print('AB_STAGE_PHYSICAL_COMMAND_COMPLETE',marker,flush=True)

def pyvalidate(script,fixture,out,marker):
    p=subprocess.run([sys.executable,str(script),fixture,str(out)],capture_output=True,text=True)
    (out/'validator.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    assert p.returncode==0 and marker in p.stdout,(fixture,p.stdout,p.stderr)
    print('AB_NUMERIC_PASS',out.name,flush=True)

def check_timing(tag):
    protocol=read(ROOT/'protocol.json');c=protocol['configs'][tag];records=[];seen=set()
    fixtures=[r for r in protocol['fixtures'] if r['kind']=='validation']
    for fixture in fixtures:
        name=fixture['name'];hashpath=Q/'runtime/cases'/name/'input400.u32'
        from build_road_arm_probe import fnv
        expected=fnv(hashpath.read_bytes())
        for repeat in range(4):
            p=ROOT/(tag+'_timing')/name/f'run{repeat}_mailbox.bin';m=struct.unpack('<39I',p.read_bytes())
            assert m[0]==0x524F4144 and m[1]==c['version'] and m[2]==3 and m[6]==0 and m[14]==0 and m[28]==0 and m[16]==expected and m[17]==c['weight_fnv']
            assert m[4] not in seen;seen.add(m[4]);assert m[18]>0 and m[30]==0x7084 and m[35]==0 and m[38]==2
            def seconds(i):return (m[i]+m[i+1]*2**32)/m[18]
            records.append(dict(fixture=name,repeat=repeat,warmup=repeat==0,sequence=m[4],boxes=m[15],total_seconds=seconds(19),network_seconds=seconds(21),preprocess_seconds=seconds(23),post_seconds=seconds(25),render_seconds=seconds(33),trace_disabled=True,mailbox_sha256=sha(p)))
    write(ROOT/(tag+'_timing_verified.json'),dict(status='ACTUAL_BOARD_TIMING_6_IMAGES_1_WARMUP_3_MEASUREMENTS_EACH',model=tag,records=records,
         elf_sha256=c['elf_sha'],weights_sha256=c['model_sha'],network_includes_trace=False,sd_written=False))
    print('AB_TIMING_VALIDATED',tag,len(records),flush=True)

def main():
    started=time.monotonic();fixtures=read(ROOT/'protocol.json')['fixtures']
    # The full Q8 batch was launched explicitly in the calling chat. Wait for its completion marker.
    log=ROOT/'q8_full.log'
    while True:
        text=log.read_text(errors='replace') if log.exists() else ''
        if 'ROAD_AB_BATCH_FAILED' in text:raise RuntimeError(text[-3000:])
        if 'ROAD_AB_BATCH_COMPLETE q8 full' in text:break
        if time.monotonic()-started>2400:raise TimeoutError('Existing Q8 readback did not finish')
        time.sleep(2)
    for f in fixtures:
        pyvalidate(ROOT/'validate_q8_ab.py',f['name'],ROOT/'q8_full'/f['name'],'ROAD_Q8_PHYSICAL_ALL86_AND_FRAME_PASS')
    write(ROOT/'q8_full_verified.json',dict(status='ALL8_PHYSICAL_Q8_ALL86_LAYERS_AND_HEADS_NMS_LCD_PASS',fixtures=[f['name'] for f in fixtures]))
    xsct(ROOT/'q8_batch.tcl',['timing'],ROOT/'q8_timing.log','ROAD_AB_BATCH_COMPLETE q8 timing');check_timing('q8')
    xsct(FP/'install_ram.tcl',[fixtures[0]['name'],1,ROOT/'fp32_first'],ROOT/'fp32_initial_download.log','ROAD_LCD_PHYSICAL_READBACK_COMPLETE')
    pyvalidate(HERE/'validate_road_lcd_static.py',fixtures[0]['name'],ROOT/'fp32_first','ROAD_LCD_PHYSICAL_NUMERIC_AND_FRAMEBUFFER_PASS')
    xsct(ROOT/'fp32_batch.tcl',['full'],ROOT/'fp32_full.log','ROAD_AB_BATCH_COMPLETE fp32 full')
    for f in fixtures:
        out=ROOT/'fp32_full'/f['name'];m=struct.unpack('<39I',(out/'mailbox.bin').read_bytes());assert m[4]==read(out/'job.json')['sequence']
        pyvalidate(HERE/'validate_road_lcd_static.py',f['name'],out,'ROAD_LCD_PHYSICAL_NUMERIC_AND_FRAMEBUFFER_PASS')
    write(ROOT/'fp32_full_verified.json',dict(status='ALL8_PHYSICAL_FP32_HEADS_DECODE_NMS_AND_LCD_PASS',fixtures=[f['name'] for f in fixtures]))
    xsct(ROOT/'fp32_batch.tcl',['timing'],ROOT/'fp32_timing.log','ROAD_AB_BATCH_COMPLETE fp32 timing');check_timing('fp32')
    xsct(FP/'switch_photo.tcl',[1,ROOT/'final_fp32_photo01'],ROOT/'final_fp32_restore.log','ROAD_LCD_PHOTO_SWITCH_COMPLETE')
    pyvalidate(HERE/'validate_road_lcd_static.py',fixtures[0]['name'],ROOT/'final_fp32_photo01','ROAD_LCD_PHYSICAL_NUMERIC_AND_FRAMEBUFFER_PASS')
    write(ROOT/'workflow_complete.json',dict(status='PHYSICAL_AB_ALL_NUMERICS_TIMINGS_AND_ORIGINAL_FP32_FINAL_DISPLAY_VERIFIED',seconds=time.monotonic()-started,
         current_model='Original FP32',current_photo=fixtures[0]['name'],all_operations='JTAG RAM only; no SD orFlash writes',sd_written=False))
    print('ROAD_PHYSICAL_AB_WORKFLOW_COMPLETE',flush=True)
if __name__=='__main__':main()
