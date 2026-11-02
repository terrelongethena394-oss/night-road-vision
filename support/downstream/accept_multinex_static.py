"""Offline gate for this isolated candidate; board correctness is a separate stage."""
from pathlib import Path
import re,json,struct,hashlib,zipfile,xml.etree.ElementTree as ET,shutil
ROOT=Path('E:/FPGA_Enhance_Work/multinex_static_20261025')
HLS=Path('E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert 'MULTINEX_STATIC_PHYSICAL_BUILD_PASS' in (ROOT/'build.log').read_text(errors='replace')
    assert 'MULTINEX_STATIC_ARM_BUILD_PASS' in (ROOT/'build_app.log').read_text(errors='replace')
    assert 'MULTINEX_STATIC_PHYSICAL_AUDIT_COMPLETE' in (ROOT/'audit_console.log').read_text(errors='replace')
    phy=(ROOT/'physical_audit.txt').read_text()
    setup=float(re.search(r'GLOBAL_SETUP_SLACK ([\d.-]+)',phy)[1]);hold=float(re.search(r'GLOBAL_HOLD_SLACK ([\d.-]+)',phy)[1])
    assert setup>=0 and hold>=0
    assert 'PERIOD_NS 10.000' in phy
    skew=(ROOT/'bus_skew.rpt').read_text()
    margins=[float(v) for v in re.findall(r'Slack \(MET\)\s*:\s*([\d.-]+)ns',skew)]
    assert margins and min(margins)>=0 and 'Slack (VIOLATED)' not in skew
    drc=(ROOT/'drc.rpt').read_text();assert not re.search(r'^\|[^\n]*\|\s*(Error|Critical Warning)\s*\|',drc,re.M)
    util=(ROOT/'utilization.rpt').read_text()
    def resource(name):return float(re.search(r'^\|\s*'+re.escape(name)+r'\s*\|\s*([\d.]+)',util,re.M)[1])
    resources={n:resource(n) for n in ('Slice LUTs','Slice Registers','Block RAM Tile','DSPs')}
    assert resources['Slice LUTs']<=53200 and resources['Block RAM Tile']<=140 and resources['DSPs']<=220
    with zipfile.ZipFile(ROOT/'multinex_static.xsa') as z:
        assert z.testzip() is None
        assert z.read('multinex_static.bit')==(ROOT/'multinex_static.bit').read_bytes()
        hwh=ET.fromstring(z.read('system.hwh'))
    module=next(a for a in hwh.iter('MODULE') if a.get('INSTANCE')=='multinex_0')
    assert module.get('VLNV')=='fpga.user:hls:multinex_fused:1.0'
    routes=list(module.iter('MEMRANGE'))
    assert {a.get('MASTERBUSINTERFACE') for a in routes}=={'m_axi_rgb_in','m_axi_rgb_out','m_axi_features_mem','m_axi_diagnostics_mem'}
    assert all(a.get('INSTANCE')=='processing_system7_0' and a.get('SLAVEBUSINTERFACE')=='S_AXI_HP0' and int(a.get('BASEVALUE'),16)==0 for a in routes)
    cpu=next(a for a in hwh.iter('MODULE') if a.get('INSTANCE')=='processing_system7_0')
    seg=next(a for a in cpu.iter('MEMRANGE') if a.get('INSTANCE')=='multinex_0')
    assert int(seg.get('BASEVALUE'),16)==0x43c20000
    old=json.loads((HLS/'completion.json').read_text(encoding='utf-8'))
    for p in old['preserved']:assert sha(Path(p['path']))==p['sha256']
    assert sha(ROOT/'ps7_init.tcl')=='d474422bbe07d4e96bc84d19b8d9574bb3483004b0bf97d47f3ce6e0930802e7'
    elf=(ROOT/'multinex_static.elf').read_bytes();assert elf[:5]==b'\x7fELF\x01'
    assert b'MULTINEX_STATIC_READY' in elf
    phoff=struct.unpack_from('<I',elf,28)[0];ents,count=struct.unpack_from('<HH',elf,42);regions=[]
    for i in range(count):
        kind,off,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',elf,phoff+i*ents)
        if kind==1 and memsz:
            assert 0x00100000<=paddr<paddr+memsz<=0x01000000
            regions.append([paddr,paddr+memsz])
    for name in ('LICENSE','NOTICE','MODEL_CARD.md','THIRD_PARTY_NOTICES.md'):shutil.copy2(HLS/name,ROOT/name)
    result=dict(status='OFFLINE_ACCEPTED_FOR_VOLATILE_JTAG_TEST_NOT_BOARD_VERIFIED',resources=resources,
        setup_slack_ns=setup,hold_slack_ns=hold,bus_skew_min_slack_ns=min(margins),clock_mhz=100,
        elf_regions=regions,bit_sha256=sha(ROOT/'multinex_static.bit'),elf_sha256=sha(ROOT/'multinex_static.elf'),
        xsa_sha256=sha(ROOT/'multinex_static.xsa'),ps7_init_sha256=sha(ROOT/'ps7_init.tcl'),
        old_preserved=old['preserved'],core='fpga.user:hls:multinex_fused:1.0',sd_written=False,
        limitation='Existing board constraints leave external input/output delays incomplete; clock-placement warning inherited. No new full external-interface closure claim. Board numerical/timing validation required.')
    (ROOT/'offline_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'ACCEPTED_FOR_JTAG.txt').write_text('Offline checks passed; not physical board numerical verification.\n'+json.dumps(result,indent=2),encoding='utf-8')
    for name in ('accept_multinex_static.py','prepare_multinex_static.py','prepare_multinex_static_app.py','prepare_multinex_static_cases.py'):
        if (HERE/name).resolve() != (ROOT/name).resolve():
            shutil.copy2(HERE/name,ROOT/name)
    print('OFFLINE_JTAG_TEST_GATE_PASS',json.dumps(resources),setup,hold,flush=True)
if __name__=='__main__':main()
