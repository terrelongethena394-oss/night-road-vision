"""Stage fast-core export/integration without touching the verified baseline."""
from pathlib import Path
import json,re,hashlib,zipfile,shutil,sys,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
BASE=Path('E:/FPGA_Enhance_Work')
HLS=BASE/'multinex_hls_r4d_20261026'
ROOT=BASE/'multinex_fast_static_r4d_20261026'
OLD=BASE/'multinex_static_20261025'
VLNV='fpga.user:hls:multinex_fast:1.0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    mode=sys.argv[1]
    if mode=='export':
        assert 'MULTINEX_COSIM_COMPLETE' in (HLS/'cosim.log').read_text(errors='replace')
        assert json.loads((HLS/'rtl_dump_audit.json').read_text())['status']=='ALL_CHECKED_RTL_OUTPUTS_EXACT'
        (HLS/'export.tcl').write_text('''set root [file dirname [file normalize [info script]]]
cd $root
open_project multinex_project
open_solution solution_100mhz
export_design -format ip_catalog -rtl verilog -vendor fpga.user -library hls -version 1.0 -ipname multinex_fast
puts "MULTINEX_FAST_EXPORT_COMPLETE"
exit
''',encoding='ascii')
    elif mode=='revision1':
        ip=HLS/'multinex_project/solution_100mhz/impl/ip'
        old=(ip/'run_ippack.tcl').read_text('utf-8')
        new,n=re.subn(r'^set Revision\s+"[^"\r\n]+"','set Revision "1"',old,flags=re.M);assert n==1
        new=new.replace('ipx::save_core $core','ipx::check_integrity -quiet $core\nipx::save_core $core')+'\nputs "MULTINEX_FAST_LOCAL_PACKAGE_COMPLETE"\n'
        (ip/'run_ippack_revision1.tcl').write_text(new,encoding='utf-8')
    elif mode=='verify_hls':
        log=(HLS/'build.log').read_text(errors='replace');assert 'HLS_C_TESTBENCH_ALL_EXACT cases=9 pixels=627908' in log and 'MULTINEX_CSIM_SYNTH_COMPLETE' in log
        assert 'C/RTL co-simulation finished: PASS' in (HLS/'cosim.log').read_text(errors='replace')
        assert json.loads((HLS/'rtl_dump_audit.json').read_text())['status']=='ALL_CHECKED_RTL_OUTPUTS_EXACT'
        ip=HLS/'multinex_project/solution_100mhz/impl/ip';xml=ET.parse(ip/'component.xml').getroot();ns={'s':xml.tag.split('}')[0][1:]}
        assert 'MULTINEX_FAST_LOCAL_PACKAGE_COMPLETE' in (ip/'package_console.log').read_text(errors='replace')
        identity=':'.join(xml.findtext('s:'+k,namespaces=ns) for k in ('vendor','library','name','version'));assert identity==VLNV
        package=ip/'fpga_user_hls_multinex_fast_1_0.zip'
        with zipfile.ZipFile(package) as z:
            assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
            for f in xml.findall('.//s:file',ns):assert f.findtext('s:name',namespaces=ns).replace('\\','/') in z.namelist()
        previous=json.loads((BASE/'multinex_hls_r3b_20261025/completion.json').read_text(encoding='utf-8'))
        assert sha(HLS/'hls_parameters.h')==previous['parameters_sha256']
        x=ET.parse(HLS/'multinex_project/solution_100mhz/syn/report/multinex_hls_csynth.xml').getroot()
        resources={a.tag:int(a.text) for a in x.find('AreaEstimates/Resources')}
        assert resources['DSP']<=220 and resources['BRAM_18K']<=280,resources
        state=dict(status='FAST_HLS_CSIM_RTL_IP_VERIFIED_NOT_DEPLOYED',vlnv=VLNV,resources=resources,
            preserved=previous['preserved'],parameters_sha256=sha(HLS/'hls_parameters.h'),dense_weights_sha256=sha(HLS/'dense_weights.h'),
            original_board_bit_sha256=sha(OLD/'multinex_static.bit'),ip_archive_sha256=sha(package),sd_written=False,
            lut_estimate_exceeds_device=resources['LUT']>53200,
            area_note='HLS LUT estimate is over budget; no fit assertion. Original r3b physical synthesis was materially smaller than HLS estimate. Require actual Vivado fit and timing before launch.')
        (HLS/'completion.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print('FAST_HLS_VERIFIED',json.dumps(resources),flush=True)
    elif mode=='prepare_board':
        assert (HLS/'completion.json').exists() and not (ROOT/'prj').exists()
        ROOT.mkdir(exist_ok=True)
        t=(HERE/'build_multinex_static.tcl').read_text('ascii').replace(OLD.as_posix(),ROOT.as_posix()).replace('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025',HLS.as_posix()).replace('fpga.user:hls:multinex_fused:1.0',VLNV)
        (ROOT/'build_board.tcl').write_text(t,encoding='ascii')
        # External hardware/software contract is unchanged; reuse the proven ARM binary.
        for n in ('multinex_static.elf','memory_map.json','start_multinex_static.tcl','run_multinex_static.tcl','case_manifest.json','cases.tcl','validate_multinex_readback.py','validator_selfcheck.json'):
            shutil.copy2(OLD/n,ROOT/n)
        for n in ('inputs','expected','app_src'):shutil.copytree(OLD/n,ROOT/n,dirs_exist_ok=True)
        (ROOT/'software_reuse.json').write_text(json.dumps(dict(reason='Same PS, LCD/VDMA addresses and control/buffer ABI; will verify new XSA and PS init before any launch.',
            original_elf_sha256=sha(OLD/'multinex_static.elf'),elf_sha256=sha(ROOT/'multinex_static.elf')),indent=2),encoding='utf-8')
        for n in ('LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md'):shutil.copy2(HLS/n,ROOT/n)
        print('FAST_STATIC_PROJECT_PREPARED',ROOT,flush=True)
    elif mode=='accept_board':
        with zipfile.ZipFile(ROOT/'multinex_static.xsa') as z:
            assert z.testzip() is None and z.read('multinex_static.bit')==(ROOT/'multinex_static.bit').read_bytes()
            h=ET.fromstring(z.read('system.hwh'));core=next(a for a in h.iter('MODULE') if a.get('INSTANCE')=='multinex_0')
            assert core.get('VLNV')==VLNV
            (ROOT/'ps7_init.tcl').write_bytes(z.read('ps7_init.tcl'))
        assert sha(ROOT/'ps7_init.tcl')==sha(OLD/'ps7_init.tcl')
        hw=HLS/'multinex_project/solution_100mhz/impl/ip/drivers/multinex_hls_v1_0/src/xmultinex_hls_hw.h'
        assert hw.read_bytes()==(OLD/'app_src/xmultinex_hls_hw.h').read_bytes()
        assert sha(ROOT/'multinex_static.elf')==sha(OLD/'multinex_static.elf')
        audit=(HERE/'audit_multinex_static.tcl').read_text('ascii').replace(OLD.as_posix(),ROOT.as_posix())
        (ROOT/'audit_physical.tcl').write_text(audit,encoding='ascii')
        accept=(HERE/'accept_multinex_static.py').read_text('utf-8').replace(OLD.as_posix(),ROOT.as_posix()).replace('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025',HLS.as_posix()).replace('fpga.user:hls:multinex_fused:1.0',VLNV)
        (ROOT/'accept_multinex_static.py').write_text(accept,encoding='utf-8')
        for n in ('prepare_multinex_static.py','prepare_multinex_static_app.py','prepare_multinex_static_cases.py'):
            shutil.copy2(HERE/n,ROOT/n)
        # Gate checks expect a successful ARM build. Record the exact ABI-compatible reuse,
        # rather than claiming a second compilation took place.
        (ROOT/'build_app.log').write_text('MULTINEX_STATIC_ARM_BUILD_PASS: reused previously compiled, board-verified ELF; MMIO ABI, PS init and addresses checked.\n',encoding='ascii')
        print('FAST_ABI_AND_SOFTWARE_REUSE_VERIFIED; run audit then acceptance',flush=True)
    else:raise ValueError(mode)
if __name__=='__main__':main()
