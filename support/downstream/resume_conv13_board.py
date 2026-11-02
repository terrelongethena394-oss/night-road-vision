"""Resume isolated project after successful Tcl-library initialization probe."""
import re,subprocess
from build_road_conv13 import ROOT,VIVADO,finalize

def main():
    assert 'BD_REOPEN_PROBE_PASS 15' in (ROOT/'probe_reopen_console.log').read_text(errors='replace')
    assert not (ROOT/'resume_build_console.log').exists()
    script=(ROOT/'build_board.tcl').read_text()
    prefix='set ::env(TCL_LIBRARY) [info library]\nset_param general.maxThreads 2\n'
    for name in ['root','official','ip']:
        prefix+=re.search(r'^set '+name+r' .+$',script,re.M)[0]+'\n'
    prefix+='open_project $root/prj/road_conv.xpr\nset bd [get_files */system.bd]\nopen_bd_design $bd\n'
    start=script.index('foreach pin {axi_vdma_0/M_AXIS_MM2S')
    (ROOT/'resume_build.tcl').write_text(prefix+script[start:],encoding='ascii')
    with (ROOT/'resume_build_console.log').open('w') as f:
        p=subprocess.run([VIVADO,'-mode','batch','-source',str(ROOT/'resume_build.tcl'),'-log',str(ROOT/'resume_build.log'),'-journal',str(ROOT/'resume_build.jou')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
    assert p.returncode==0 and 'ROAD_CONV_BOARD_OFFLINE_BUILD_PASS' in (ROOT/'resume_build_console.log').read_text(errors='replace')
    finalize()

if __name__=='__main__':main()
