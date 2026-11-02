"""Accept C/RTL simulation, package shared IP, route isolated camera design."""
from pathlib import Path
import csv,json,re,shutil,subprocess,zipfile
from prepare_fp32_cpu_pack import BASE,read,write,sha
from prepare_road_conv13 import ROOT as HLS
ROOT=BASE/'road_conv13_board_20261028_r2'
OLD=BASE/'road_conv_burst_board_20261027'
HLS_EXE='E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat'
VIVADO='E:/Xilinx/Vivado/2020.2/bin/vivado.bat'
PE=8
SNAPSHOT=BASE/'road_conv13_package_20261028_r1'
def checked_status():return 'SHARED13_ALL58_CSIM_ALL9_RTL_BYTE_EXACT_EXPORTED' if PE==8 else 'SHARED13_P16_CSIM_RTL_BYTE_EXACT_EXPORTED'

def finish_hls(ip_override=None):
    policy=read(HLS/'protocol.json')
    csim=list(csv.DictReader((HLS/'tb_csim.csv').open()));rtl=list(csv.DictReader((HLS/'tb_rtl.csv').open()))
    assert len(csim)==policy['fixtures'] and len(rtl)==policy['rtl_fixtures']
    assert all(int(v['bit_differences'])==0 for v in csim+rtl)
    for stage,marker in [('csim','ROAD_CONV3_CSIM_COMPLETE_P8'),('synth','ROAD_CONV3_SYNTH_COMPLETE_P8'),('cosim','ROAD_CONV3_COSIM_COMPLETE_P8')]:
        marker=marker.replace('P8',f'P{PE}');log=(HLS/(stage+'.log')).read_text(errors='replace');assert marker in log and 'ERROR:' not in log,stage
    sol=HLS/'conv_project/solution_100mhz';rpt=(sol/'syn/report/road_conv3_fp32_csynth.rpt').read_text()
    mac=[v for v in rpt.splitlines() if '+++ MAC_INTERLEAVED' in v];assert len(mac)==1 and re.search(r'\|\s*1\s*\|\s*1\s*\|',mac[0]),mac
    assert 'Pass' in (sol/'sim/report/road_conv3_fp32_cosim.rpt').read_text()
    if ip_override is None:
        with (HLS/'export.log').open('w') as f:subprocess.run([HLS_EXE,'-f',str(HLS/'export.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=600)
    ip=Path(ip_override) if ip_override is not None else sol/'impl/ip';archive=ip/f'fpga_user_hls_road_conv13_p{PE}_1_0.zip'
    if ip_override is not None:
        proof=read(SNAPSHOT/'snapshot.json')
        for name,digest in proof['rtl_sha256'].items():assert sha(sol/'syn/verilog'/name)==digest
        assert sha(archive)==proof['archive_sha256']
    if not archive.exists():
        original=(ip/'run_ippack.tcl').read_text();revision=re.search(r'^set Revision\s+"?(\d+)',original,re.M)
        assert revision and int(revision[1])>2147483647,'Only known project-local date revision overflow is repairable here'
        fixed=re.sub(r'^set Revision\s+.*$','set Revision "1"',original,count=1,flags=re.M)
        (ip/'run_ippack_revisionfix.tcl').write_text(fixed,encoding='ascii')
        with (HLS/'package_console.log').open('w') as f:subprocess.run([VIVADO,'-mode','batch','-source',str(ip/'run_ippack_revisionfix.tcl'),'-log',str(HLS/'package.log'),'-journal',str(HLS/'package.jou')],cwd=ip,stdout=f,stderr=subprocess.STDOUT,timeout=600)
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
    driver=ip/'drivers/road_conv3_fp32_v1_0/src/xroad_conv3_fp32_hw.h'
    def regs(p):return dict(re.findall(r'^#define\s+(XROAD_CONV3_FP32_CONTROL_\w+)\s+(\w+)',p.read_text(),re.M))
    old=regs(BASE/'road_detail_board_20261028_r1/firmware/source/xroad_conv3_fp32_hw.h');new=regs(driver)
    assert all(new.get(k)==v for k,v in old.items())
    assert set(new)-set(old)=={'XROAD_CONV3_FP32_CONTROL_ADDR_KERNEL_DATA','XROAD_CONV3_FP32_CONTROL_BITS_KERNEL_DATA'}
    write(HLS/'checked.json',dict(status=checked_status(),pe=PE,csim=csim,rtl=rtl,mac_loop=mac[0],archive=str(archive),archive_sha256=sha(archive),driver_path=str(driver),driver_sha256=sha(driver),registers=new,source_sha256={n:sha(HLS/n) for n in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']},sd_written=False))
    return ip

def route(ip):
    if ROOT.exists():
        assert not (ROOT/'prj').exists() and not (ROOT/'build_console.log').exists(),'Preserve existing build'
    else:ROOT.mkdir(exist_ok=False)
    script=(OLD/'build_board.tcl').read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace((BASE/'road_conv_burst_hls_20261027/conv_project/solution_100mhz/impl/ip').as_posix(),ip.as_posix()).replace('fpga.user:hls:road_conv3_burst_p8:1.0','fpga.user:hls:road_conv13_p8:1.0')
    script='set ::env(TCL_LIBRARY) [info library]\n'+script
    assert 'road_conv3_burst_p8:1.0' not in script and 'road_conv13_p8:1.0' in script
    cache=OLD/'ipcache';assert cache.is_dir()
    shutil.copytree(cache,ROOT/'ipcache')
    (ROOT/'build_board.tcl').write_text(script,encoding='ascii')
    write(ROOT/'protocol.json',dict(status='SHARED13_ROUTE_PENDING',source_bd=str(OLD/'prj/road_conv.srcs/sources_1/bd/system/system.bd'),hls=str(HLS),hls_checked_sha256=sha(HLS/'checked.json') if (HLS/'checked.json').exists() else None,sd_written=False,hardware_downloaded=False))
    with (ROOT/'build_console.log').open('w') as f:
        p=subprocess.run([VIVADO,'-mode','batch','-source',str(ROOT/'build_board.tcl'),'-log',str(ROOT/'build_vivado.log'),'-journal',str(ROOT/'build_vivado.jou')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
    assert p.returncode==0 and 'ROAD_CONV_BOARD_OFFLINE_BUILD_PASS' in (ROOT/'build_console.log').read_text(errors='replace')
    finalize()

def finalize():
    values=dict(v.split('=',1) for v in (ROOT/'timing_acceptance.txt').read_text().splitlines())
    assert float(values['WNS'])>=0 and float(values['WHS'])>=0 and int(values['ROAD_CONV_DSP'])>0
    new=read(ROOT/'prj/road_conv.srcs/sources_1/bd/system/system.bd')['design'];old=read(OLD/'prj/road_conv.srcs/sources_1/bd/system/system.bd')['design']
    assert new['components']['processing_system7_0']['parameters']==old['components']['processing_system7_0']['parameters'],'PS/BSP configuration changed'
    seg=new['addressing']['/processing_system7_0']['address_spaces']['Data']['segments']['SEG_road_conv_0_Reg'];assert int(seg['offset'],16)==0x43C30000
    for space in new['addressing']['/road_conv_0']['address_spaces'].values():
        entries=list(space['segments'].values());assert len(entries)==1 and entries[0]['range']=='1G' and int(entries[0]['offset'],16)==0
    with zipfile.ZipFile(ROOT/'road_conv.xsa') as z:
        assert z.testzip() is None
        ps=[n for n in z.namelist() if Path(n).name=='ps7_init.tcl'];bits=[n for n in z.namelist() if n.endswith('.bit')]
        assert len(ps)==len(bits)==1
        raw=z.read(ps[0]);assert raw.decode().splitlines()==(BASE/'road_detail_board_20261028_r1/firmware/ps7_init.tcl').read_text().splitlines()
        (ROOT/'ps7_init.tcl').write_bytes(raw)
        import hashlib
        assert hashlib.sha256(z.read(bits[0])).hexdigest()==sha(ROOT/'road_conv.bit')
    timing=(ROOT/'timing_summary.rpt').read_text();assert 'All user specified timing constraints are met.' in timing
    checks={k:int(re.search(r'checking '+k+r' \((\d+)\)',timing)[1]) for k in ['no_clock','unconstrained_internal_endpoints','no_input_delay','no_output_delay','loops']}
    assert checks['no_clock']==checks['unconstrained_internal_endpoints']==checks['loops']==0
    assert not re.search(r'\b(?:Error|Critical Warning)\b',(ROOT/'drc.rpt').read_text())
    util=(ROOT/'utilization.rpt').read_text()
    resources={k:float(re.search(r'^\|\s*'+re.escape(v)+r'\s*\|\s*([\d.]+)\s*\|',util,re.M)[1]) for k,v in [('LUT','Slice LUTs'),('FF','Slice Registers'),('BRAM36','Block RAM Tile'),('DSP','DSPs')]}
    checked=(HLS/'checked.json').exists() and read(HLS/'checked.json')['status']==checked_status()
    write(ROOT/'offline_complete.json',dict(status='SHARED13_ROUTED_AND_TIMING_PASSED_NOT_BOARD_TESTED' if checked else 'ROUTED_TIMING_PASSED_RTL_STILL_PENDING',wns_ns=float(values['WNS']),whs_ns=float(values['WHS']),resources=resources,timing_checks=checks,external_io_timing_fully_specified=False,ps_config_unchanged=True,bit_sha256=sha(ROOT/'road_conv.bit'),xsa_sha256=sha(ROOT/'road_conv.xsa'),hls_sha256=sha(HLS/'checked.json') if checked else None,sd_written=False))
    print('SHARED13_ROUTED_OFFLINE_PASS',resources,flush=True)

if __name__=='__main__':route(finish_hls())
