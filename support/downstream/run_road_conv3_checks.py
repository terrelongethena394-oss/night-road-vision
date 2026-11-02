"""Serial per-project HLS checks; errors require intervention, not optimistic exit codes."""
from pathlib import Path
import subprocess,csv,time
from prepare_road_conv3_hls import ROOT,read,write,sha
HLS=Path('E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat')

def invoke(d,stage,logname,marker):
    log=d/logname;assert not log.exists()
    with log.open('w') as f:p=subprocess.run([str(HLS),'-f',str(d/(stage+'.tcl'))],stdout=f,stderr=subprocess.STDOUT)
    text=log.read_text(errors='replace');assert marker in text and 'ERROR:' not in text,(str(log),p.returncode,text[-4000:])
    print('HLS_STAGE_PASS',d.name,stage,flush=True)

def main():
    records=[]
    for pe in [4,8]:
        d=ROOT/f'p{pe}';invoke(d,'csim','csim_r2.log',f'ROAD_CONV3_CSIM_COMPLETE_P{pe}')
        rows=list(csv.DictReader((d/'tb_csim.csv').open()));assert len(rows)==11 and all(int(r['bit_differences'])==0 for r in rows)
        invoke(d,'cosim','cosim_r2.log',f'ROAD_CONV3_COSIM_COMPLETE_P{pe}')
        report=d/'conv_project/solution_100mhz/sim/report/road_conv3_fp32_cosim.rpt';text=report.read_text();assert 'Verilog' in text and 'Pass' in text
        rtl=list(csv.DictReader((d/'tb_rtl.csv').open()));assert len(rtl)==4 and all(float(r['max_abs'])<=2e-4 for r in rtl)
        r=dict(pe=pe,status='CSIM_ALL11_AND_VERILOG_COSIM_ALL4_PLUS_INVALID_GUARDS_PASS',csim=rows,rtl=rtl,
             source_sha256={n:sha(d/n) for n in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']},cosim_report_sha256=sha(report),hardware_access=False)
        write(d/'checked.json',r);records.append(r);print('ROAD_CONV3_VARIANT_PHYSICAL_RTL_MODEL_PASS',pe,flush=True)
    write(ROOT/'checks_complete.json',dict(status='P4_P8_C_AND_RTL_CHECKS_COMPLETE_NOT_BOARD_TESTED',variants=records,hardware_access=False,sd_written=False))
    print('ROAD_CONV3_ALL_VARIANTS_CHECKED',flush=True)
if __name__=='__main__':main()
