"""Run R2 offline gates, package IP with project-local date-revision repair."""
from pathlib import Path
import csv,hashlib,json,re,subprocess,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027')
HLS='E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat'
VIVADO='E:/Xilinx/Vivado/2020.2/bin/vivado.bat'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def invoke(stage,marker,allow_revision_error=False):
    log=ROOT/(stage+'.log');assert not log.exists()
    with log.open('w') as f:p=subprocess.run([HLS,'-f',str(ROOT/(stage+'.tcl'))],stdout=f,stderr=subprocess.STDOUT)
    text=log.read_text(errors='replace')
    if not allow_revision_error:assert marker in text and 'ERROR:' not in text,(stage,text[-3000:])
    print('ROAD_BURST_STAGE_FINISHED',stage,p.returncode,flush=True)
def main():
    invoke('csim','ROAD_CONV3_CSIM_COMPLETE_P8')
    rows=list(csv.DictReader((ROOT/'tb_csim.csv').open()));assert len(rows)==11 and all(int(r['bit_differences'])==0 for r in rows)
    invoke('synth','ROAD_CONV3_SYNTH_COMPLETE_P8')
    solution=ROOT/'conv_project/solution_100mhz'
    report=(solution/'syn/report/road_conv3_fp32_csynth.rpt').read_text()
    mac=[line for line in report.splitlines() if '++ MAC_INTERLEAVED' in line];assert len(mac)==1
    assert re.search(r'\|\s*1\s*\|\s*1\s*\|',mac[0]),mac[0]
    rtl=(solution/'syn/verilog/road_conv3_fp32.v').read_text()
    input_adapter=rtl[rtl.index('    .ARLEN(m_axi_gmem_in_ARLEN)'):rtl.index('    .ARLEN(m_axi_gmem_w_ARLEN)')]
    ar=re.search(r'\.I_ARLEN\(([^)]+)\)',input_adapter);assert ar and ar[1]!="32'd1",'Input still single-beat'
    (ROOT/'burst_inference.json').write_text(json.dumps(dict(status='GENERATED_RTL_INPUT_BURST_LENGTH_VARIABLE',i_arlen=ar[1],mac_loop=mac[0],rtl_sha256=sha(solution/'syn/verilog/road_conv3_fp32.v'),hardware_access=False),indent=2),encoding='utf-8')
    invoke('cosim','ROAD_CONV3_COSIM_COMPLETE_P8')
    rows_rtl=list(csv.DictReader((ROOT/'tb_rtl.csv').open()));assert len(rows_rtl)==4 and all(int(r['bit_differences'])==0 for r in rows_rtl)
    cosim=solution/'sim/report/road_conv3_fp32_cosim.rpt';assert 'Pass' in cosim.read_text()
    invoke('export','ROAD_CONV3_EXPORT_COMPLETE_P8',True)
    ip=solution/'impl/ip';archive=ip/'fpga_user_hls_road_conv3_burst_p8_1_0.zip'
    if not archive.exists():
        original=(ip/'run_ippack.tcl').read_text();revision=re.search(r'^set Revision\s+"?(\d+)',original,re.M);assert revision and int(revision[1])>2147483647
        fixed=re.sub(r'^set Revision\s+.*$','set Revision "1"',original,count=1,flags=re.M)
        (ip/'run_ippack_revisionfix.tcl').write_text(fixed)
        with (ROOT/'package_console.log').open('w') as f:subprocess.run([VIVADO,'-mode','batch','-source',str(ip/'run_ippack_revisionfix.tcl'),'-log',str(ROOT/'package_vivado.log'),'-journal',str(ROOT/'package_vivado.jou')],cwd=ip,stdout=f,stderr=subprocess.STDOUT)
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
    proof=dict(status='R2_CSIM_11_RTL_COSIM_4_PLUS_GUARDS_AND_BURST_INFERENCE_VERIFIED_NOT_BOARD_TESTED',csim=rows,rtl=rows_rtl,archive=str(archive),archive_sha256=sha(archive),source_sha256={n:sha(ROOT/n) for n in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']},hardware_access=False,sd_written=False)
    (ROOT/'checked.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print('ROAD_CONV_BURST_R2_OFFLINE_IP_PASS',flush=True)
if __name__=='__main__':main()
