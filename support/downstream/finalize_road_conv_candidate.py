"""Accept routed files, audit the inherited PS configuration, package offline evidence."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
    log=(ROOT/'build_console.log').read_text(errors='replace');assert 'ROAD_CONV_BOARD_OFFLINE_BUILD_PASS' in log
    acceptance=(ROOT/'timing_acceptance.txt').read_text();values=dict(line.split('=',1) for line in acceptance.splitlines())
    assert float(values['WNS'])>=0 and float(values['WHS'])>=0 and int(values['ROAD_CONV_DSP'])>0
    current_bd=ROOT/'prj/road_conv.srcs/sources_1/bd/system/system.bd'
    new=json.loads(current_bd.read_text())['design']
    protocol=json.loads((ROOT/'protocol.json').read_text());old=json.loads(Path(protocol['source_bd']).read_text())['design']
    # Same PS7 clocks/DDR/MIO configuration permits reuse of this standalone BSP.
    a=old['components']['processing_system7_0']['parameters'];b=new['components']['processing_system7_0']['parameters']
    assert all(b.get(k)==v for k,v in a.items()),'Existing PS configuration changed; regenerate BSP'
    added={k:v for k,v in b.items() if k not in a}
    expected_added={'PCW_IRQ_F2P_MODE':{'value':'DIRECT'},**{'PCW_S_AXI_HP%d_DATA_WIDTH'%n:{'value':'64'} for n in [1,2,3]}}
    assert added==expected_added,'Unexpected regenerated PS properties'
    assert b['PCW_USE_FABRIC_INTERRUPT']['value']=='0' and all(b['PCW_USE_S_AXI_HP%d'%n]['value']=='0' for n in [1,2,3])
    assert float(b['PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ']['value'])==100
    seg=new['addressing']['/processing_system7_0']['address_spaces']['Data']['segments']['SEG_road_conv_0_Reg']
    assert int(seg['offset'],16)==0x43C30000
    for space in new['addressing']['/road_conv_0']['address_spaces'].values():
        entries=list(space['segments'].values());assert len(entries)==1 and entries[0]['range']=='1G' and int(entries[0]['offset'],16)==0
    with zipfile.ZipFile(ROOT/'road_conv.xsa') as z:
        assert z.testzip() is None
        names=z.namelist();ps=[n for n in names if Path(n).name=='ps7_init.tcl'];assert len(ps)==1
        (ROOT/'future_board_test/ps7_init.tcl').write_bytes(z.read(ps[0]))
        reference=Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/ps7_init.tcl')
        assert z.read(ps[0]).decode().splitlines()==reference.read_text().splitlines(),'PS initialization instructions changed'
        bits=[n for n in names if n.endswith('.bit')];assert len(bits)==1
        assert hashlib.sha256(z.read(bits[0])).hexdigest()==sha(ROOT/'road_conv.bit')
    util=(ROOT/'utilization.rpt').read_text()
    def resource(label):
        m=re.search(r'^\|\s*'+re.escape(label)+r'\s*\|\s*([\d.]+)\s*\|',util,re.M);assert m,label;return float(m[1])
    resources={key:resource(label) for key,label in [('lut','Slice LUTs'),('registers','Slice Registers'),('bram36_tiles','Block RAM Tile'),('dsp','DSPs')]}
    timing=(ROOT/'timing_summary.rpt').read_text()
    assert 'All user specified timing constraints are met.' in timing
    timing_checks={key:int(re.search(r'checking '+key+r' \((\d+)\)',timing)[1]) for key in ['no_clock','unconstrained_internal_endpoints','no_input_delay','no_output_delay','loops']}
    assert timing_checks['no_clock']==timing_checks['unconstrained_internal_endpoints']==timing_checks['loops']==0
    drc=(ROOT/'drc.rpt').read_text();assert not re.search(r'\b(?:Error|Critical Warning)\b',drc),'Review DRC errors before acceptance'
    drc_summary=[dict(rule=m[1],severity=m[2],count=int(m[3])) for m in re.finditer(r'^\|\s*(\S+)\s*\|\s*(Warning|Advisory)\s*\|[^\n]*?\|\s*(\d+)\s*\|',drc,re.M)]
    sources=ROOT/'source_bundle';sources.mkdir(exist_ok=False)
    for name in ['build_road_conv_board.tcl','road_conv_probe.c','build_road_conv_probe.py','prepare_road_conv_board_test.py','validate_road_conv_board.py','selfcheck_road_conv_validator.py','road_conv_preflight.py','finalize_road_conv_candidate.py','prepare_road_conv3_hls.py','road_conv3_hls.cpp','road_conv3_hls.h','road_conv3_reference.c','tb_road_conv3.cpp','run_road_conv3_checks.py','road_conv3_pack.c','prepare_road_conv3_adapter.py','package_road_conv3_ip.py']:
        shutil.copy2(HERE/name,sources/name)
    shutil.copy2(HLS/'YOLOv5_LICENSE',sources/'YOLOv5_LICENSE')
    current_camera=Path('E:/FPGA_Enhance_Work/road_camera_20261027/road_camera.elf')
    assert sha(current_camera)=='47ddf53348eacfde4f4956f53fe39b2d0637c189e8666cf6dfb476e94dd93166'
    artifacts=['road_conv.bit','road_conv.xsa','future_board_test/ps7_init.tcl','future_board_test/run_future_ram_test.tcl','future_board_test/road_conv_preflight.py','future_board_test/validate_road_conv_board.py','future_board_test/fixtures.json','arm_probe/road_conv_probe.elf','arm_probe/compile_complete.json','system_road_conv_bd.tcl','timing_acceptance.txt','utilization.rpt','timing_summary.rpt','drc.rpt']
    proof=dict(status='ROUTED_TIMING_AND_SOFTWARE_CHECKED_NOT_BOARD_TESTED',part='xc7z020clg400-2',target_clock_mhz=100,wns_ns=float(values['WNS']),whs_ns=float(values['WHS']),road_conv_dsp_cells=int(values['ROAD_CONV_DSP']),whole_test_design_resources=resources,timing_checks=timing_checks,external_io_timing_fully_specified=False,drc_summary=drc_summary,existing_ps_configuration_unchanged=True,additional_serialized_unused_defaults=added,ps_initialization_instructions_identical=True,axi_control_address=0x43C30000,axi_ddr_range_bytes=0x40000000,artifact_sha256={n:sha(ROOT/n) for n in artifacts},hardware_downloaded=False,arm_probe_executed=False,sd_written=False,current_camera_elf_sha256=sha(current_camera),full_detector_offload=False,speedup_measured=False,accuracy_change_claimed=False)
    write(ROOT/'offline_acceptance.json',proof)
    subprocess.run([sys.executable,str(ROOT/'future_board_test/road_conv_preflight.py')],check=True)
    write(ROOT/'offline_complete.json',dict(**proof,preflight_passed=True))
    print('ROAD_CONV_ROUTED_CANDIDATE_OFFLINE_ACCEPTED',json.dumps(resources),flush=True)
if __name__=='__main__':main()
