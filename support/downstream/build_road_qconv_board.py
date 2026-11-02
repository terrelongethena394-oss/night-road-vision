"""Isolated full-video hardware build; never connects to a board."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_qconv_r2_schedule_20261027')
BASE=Path('E:/FPGA_Enhance_Work/road_conv_burst_board_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finalize():
    assert 'ROAD_QCONV_BOARD_OFFLINE_BUILD_PASS' in (ROOT/'build_console.log').read_text(errors='replace')
    v=dict(line.split('=',1) for line in (ROOT/'timing_acceptance.txt').read_text().splitlines());assert float(v['WNS'])>=0 and float(v['WHS'])>=0
    new=json.loads((ROOT/'prj/road_qconv.srcs/sources_1/bd/system/system.bd').read_text())['design']
    old=json.loads(Path('E:/FPGA_Enhance_Work/camera_nn8_20261023/prj/camera_nn.srcs/sources_1/bd/system/system.bd').read_text())['design']
    a=old['components']['processing_system7_0']['parameters'];b=new['components']['processing_system7_0']['parameters'];assert all(b.get(k)==x for k,x in a.items())
    added={k:x for k,x in b.items() if k not in a};expected={'PCW_IRQ_F2P_MODE':{'value':'DIRECT'},**{'PCW_S_AXI_HP%d_DATA_WIDTH'%n:{'value':'64'} for n in [1,2,3]}};assert added==expected
    assert b['PCW_USE_FABRIC_INTERRUPT']['value']=='0' and all(b['PCW_USE_S_AXI_HP%d'%n]['value']=='0' for n in [1,2,3])
    seg=new['addressing']['/processing_system7_0']['address_spaces']['Data']['segments']['SEG_road_qconv_0_Reg'];assert int(seg['offset'],16)==0x43C30000
    spaces=new['addressing']['/road_qconv_0']['address_spaces'];assert len(spaces)==5
    for space in spaces.values():
        entries=list(space['segments'].values());assert len(entries)==1 and entries[0]['range']=='1G' and int(entries[0]['offset'],16)==0
    with zipfile.ZipFile(ROOT/'road_qconv.xsa') as z:
        assert z.testzip() is None;ps=[n for n in z.namelist() if Path(n).name=='ps7_init.tcl'];bits=[n for n in z.namelist() if n.endswith('.bit')];assert len(ps)==len(bits)==1
        data=z.read(ps[0]);assert data.decode().splitlines()==Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1/ps7_init.tcl').read_text().splitlines()
        (ROOT/'ps7_init.tcl').write_bytes(data);assert hashlib.sha256(z.read(bits[0])).hexdigest()==sha(ROOT/'road_qconv.bit')
    timing=(ROOT/'timing_summary.rpt').read_text();assert 'All user specified timing constraints are met.' in timing
    checks={k:int(re.search(r'checking '+k+r' \((\d+)\)',timing)[1]) for k in ['no_clock','unconstrained_internal_endpoints','no_input_delay','no_output_delay','loops']}
    assert checks['no_clock']==checks['unconstrained_internal_endpoints']==checks['loops']==0
    assert not re.search(r'\b(?:Error|Critical Warning)\b',(ROOT/'drc.rpt').read_text())
    util=(ROOT/'utilization.rpt').read_text();resources={}
    for key,label in [('lut','Slice LUTs'),('registers','Slice Registers'),('bram36_tiles','Block RAM Tile'),('dsp','DSPs')]:resources[key]=float(re.search(r'^\|\s*'+re.escape(label)+r'\s*\|\s*([\d.]+)\s*\|',util,re.M)[1])
    proof=dict(status='EXPERIMENTAL_INT8_DETECTOR_HARDWARE_ROUTED_NOT_BOARD_TESTED',wns_ns=float(v['WNS']),whs_ns=float(v['WHS']),resources=resources,timing_checks=checks,external_io_timing_fully_specified=False,existing_ps_config_and_initialization_unchanged=True,serialized_inactive_defaults=added,axi_ddr_ports=5,axi_control_address=0x43C30000,artifact_sha256={n:sha(ROOT/n) for n in ['road_qconv.bit','road_qconv.xsa','ps7_init.tcl','build_board.tcl','timing_summary.rpt','drc.rpt']},accuracy_gate_passed=False,default_promotion_allowed=False,hardware_access=False,sd_written=False)
    (ROOT/'offline_complete.json').write_text(json.dumps(proof,indent=2));print('ROAD_QCONV_ROUTED_ACCEPTED',resources,flush=True)
def main():
    proof=json.loads((HLS/'ip_complete.json').read_text());assert sha(proof['archive'])==proof['archive_sha256'];ROOT.mkdir(exist_ok=False)
    ip=HLS/'qconv_project/solution_100mhz/impl/ip'
    s=(BASE/'build_board.tcl').read_text().replace(BASE.as_posix(),ROOT.as_posix()).replace('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027/conv_project/solution_100mhz/impl/ip',ip.as_posix())
    s=s.replace('fpga.user:hls:road_conv3_burst_p8:1.0','fpga.user:hls:road_qconv_i8_r2:1.0').replace('road_conv','road_qconv')
    # The global identifier replacement must not corrupt the already replaced IP path.
    assert 'set ip '+ip.as_posix() in s
    s=s.replace('CONFIG.NUM_SI 5','CONFIG.NUM_SI 7').replace('{S02 gmem_in S03 gmem_w S04 gmem_out}','{S02 gmem_in S03 gmem_w S04 gmem_meta S05 gmem_table S06 gmem_out}')
    s=s.replace('ROAD_CONV','ROAD_QCONV')
    shutil.copytree(BASE/'ipcache',ROOT/'ipcache')
    (ROOT/'build_board.tcl').write_text(s,encoding='ascii')
    (ROOT/'protocol.json').write_text(json.dumps(dict(status='ISOLATED_BUILD_NO_HARDWARE_ACCESS',ip=proof,accuracy_gate_passed=False,default_promotion_allowed=False),indent=2))
    with (ROOT/'build_console.log').open('w') as f:subprocess.run(['E:/Xilinx/Vivado/2020.2/bin/vivado.bat','-mode','batch','-source',str(ROOT/'build_board.tcl'),'-log',str(ROOT/'build_vivado.log'),'-journal',str(ROOT/'build_vivado.jou')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    finalize()
if __name__=='__main__':main()
