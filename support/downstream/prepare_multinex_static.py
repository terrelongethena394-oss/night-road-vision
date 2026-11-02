"""Prepare a separate board build and restrict ARM sections below DDR buffers."""
from pathlib import Path
import json,shutil,hashlib
ROOT=Path('E:/FPGA_Enhance_Work/multinex_static_20261025')
HLS=Path('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025')
HERE=Path(__file__).resolve().parent
def main():
    assert not (ROOT/'prj').exists(),'Existing project must be preserved'
    state=json.loads((HLS/'completion.json').read_text(encoding='utf-8'))
    assert state['status']=='FUSED_CSIM_SYNTH_RTL_IP_VERIFIED_NOT_INTEGRATED'
    ROOT.mkdir(exist_ok=True)
    shutil.copy2(HERE/'build_multinex_static.tcl',ROOT/'build_board.tcl')
    ranges=dict(application=[0x00100000,0x01000000],display=[0x02000000,0x02000000+3*800*480*3],
        mailbox=[0x03000000,0x03001000],input=[0x04000000,0x04000000+800*480*4],
        output=[0x04200000,0x04200000+800*480*4],scratch=[0x04400000,0x04400000+800*480*16],diagnostics=[0x04B00000,0x04B00060])
    for a,(s,e) in ranges.items():
        for b,(s2,e2) in ranges.items():
            if a!=b:assert e<=s2 or e2<=s,(a,b)
    (ROOT/'memory_map.json').write_text(json.dumps(ranges,indent=2),encoding='utf-8')
    src=ROOT/'app_src';src.mkdir(exist_ok=True)
    old=Path('E:/FPGA_Enhance_Work/real_cnn_adaptive_verified_20261025/sources/adaptive_arm')
    for d in ('display_ctrl','vdma_api','clk_wiz'):shutil.copytree(old/d,src/d,dirs_exist_ok=True)
    linker=(old/'lscript.ld').read_text().replace('LENGTH = 0x3FF00000','LENGTH = 0x00F00000')
    assert 'LENGTH = 0x00F00000' in linker
    (src/'lscript.ld').write_text(linker,encoding='ascii')
    assert 'EnableSync = 0' in (src/'vdma_api/vdma_api.c').read_text() or 'EnableSync = 0' in (src/'vdma_api/vdma_api.c').read_text().replace('  ',' ')
    (ROOT/'build_identity.json').write_text(json.dumps(dict(stage='PREPARED_NOT_BUILT_OR_DEPLOYED',hls_root=str(HLS),memory=ranges,
        parameters_sha256=state['parameters_sha256'],hardware_downloaded=False,sd_written=False),indent=2),encoding='utf-8')
    print('STATIC_PROJECT_PREPARED',ROOT,flush=True)
if __name__=='__main__':main()
