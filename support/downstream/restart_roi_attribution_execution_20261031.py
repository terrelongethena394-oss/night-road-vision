"""Stop only this read-only study for a registered equivalent runtime speedup."""
import sys
sys.path.insert(0,'E:/FPGA_Enhance_Work/road_detector_lib')
import psutil
from road_enhanced_detection_common import read,write
from study_roi_enhancement_attribution_20261031 import ROOT
def main():
    found=[]
    for p in psutil.process_iter(['pid','cmdline']):
        try:cmd=p.info['cmdline'] or []
        except psutil.Error:continue
        if any('launch_road_cuda.py' in s for s in cmd) and any(s.endswith('study_roi_enhancement_attribution_20261031.py') for s in cmd):found.append((p,cmd))
    assert found,'No matching study process; do not stop unrelated work.'
    write(ROOT/'execution_restart_receipt.json',dict(reason='Byteexact C preprocessing plus GPU batching. No accuracy scores inspected, no transform/model/ROI/gate/selection changes. Preserve original frozen source and protocol.',prior_progress=read(ROOT/'progress.json'),processes=[{'pid':p.pid,'cmdline':cmd} for p,cmd in found],hardware_access=False,sd_written=False))
    for p,cmd in found:p.terminate()
    psutil.wait_procs([p for p,cmd in found],timeout=10)
    print('MATCHING_READONLY_STUDY_STOPPED_FOR_EQUIVALENT_RUNTIME',len(found),flush=True)
if __name__=='__main__':main()
