"""Offline C/synthesis/RTL gates for the generic exact integer convolution unit."""
from pathlib import Path
import csv,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_hls_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def invoke(stage,marker):
    log=ROOT/(stage+'_r1.log');assert not log.exists()
    with log.open('w') as f:subprocess.run(['E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat','-f',str(ROOT/(stage+'.tcl'))],stdout=f,stderr=subprocess.STDOUT)
    text=log.read_text(errors='replace');assert marker in text and 'ERROR:' not in text,(stage,text[-4000:])
    print('ROAD_QCONV_STAGE_PASS',stage,flush=True)
def main():
    invoke('csim','ROAD_QCONV_CSIM_COMPLETE');csim=list(csv.DictReader((ROOT/'tb_all.csv').open()));assert len(csim)==66 and all(int(r['byte_differences'])==0 for r in csim)
    invoke('synth','ROAD_QCONV_SYNTH_COMPLETE');solution=ROOT/'qconv_project/solution_100mhz'
    report=solution/'syn/report/road_qconv_csynth.rpt';xml=ET.parse(solution/'syn/report/road_qconv_csynth.xml').getroot()
    resources={k:int(xml.findtext('./AreaEstimates/Resources/'+k)) for k in ['BRAM_18K','DSP','FF','LUT']}
    estimated_period=float(xml.findtext('./PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod'))
    text=report.read_text();mac=[line for line in text.splitlines() if re.search(r'\bMAC\s*\|',line)];search=[line for line in text.splitlines() if re.search(r'\bSEARCH\s*\|',line)]
    assert mac and search,(mac,search)
    for line in mac+search:assert re.search(r'\|\s*1\s*\|\s*1\s*\|',line),'Pipeline target missed: '+line
    # These are HLS estimates, not place/route acceptance or measured FPS.
    assert resources['DSP']<=200 and resources['BRAM_18K']<=250 and resources['LUT']<=44000,resources
    assert estimated_period<=10.0,estimated_period
    (ROOT/'synthesis_checked.json').write_text(json.dumps(dict(status='HLS_RESOURCE_AND_II_ESTIMATES_PASS_NOT_ROUTED',resources=resources,mac=mac,search=search,hardware_access=False),indent=2),encoding='utf-8')
    invoke('cosim','ROAD_QCONV_COSIM_COMPLETE');rtl=list(csv.DictReader((ROOT/'tb_rtl.csv').open()));assert len(rtl)==6 and all(int(r['byte_differences'])==0 for r in rtl)
    cosim=solution/'sim/report/road_qconv_cosim.rpt';assert 'Pass' in cosim.read_text()
    result=dict(status='INT8_UNIT_CSIM_ALL60_REAL_PLUS6_SYNTHETIC_AND_RTL6_GUARDS_PASS_NOT_BOARD_TESTED',cropped_real_inputs=json.loads((ROOT/'protocol.json').read_text()).get('cropped_real_inputs',False),estimated_period_ns=estimated_period,csim=csim,rtl=rtl,resources=resources,source_sha256={n:sha(ROOT/n) for n in ['road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']},hardware_access=False,sd_written=False,accuracy_improvement_claimed=False,fps_claimed=False)
    (ROOT/'checked.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ROAD_QCONV_ALL_OFFLINE_UNIT_GATES_PASS',flush=True)
if __name__=='__main__':main()
