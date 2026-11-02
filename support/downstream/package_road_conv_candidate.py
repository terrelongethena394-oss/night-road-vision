"""Archive the accepted offline candidate, not a claimed board-validated release."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    proof=json.loads((ROOT/'offline_complete.json').read_text());assert not proof['hardware_downloaded'] and proof['preflight_passed']
    for n,digest in proof['artifact_sha256'].items():assert sha(ROOT/n)==digest,n
    checks=json.loads((ROOT/'validator_selfcheck.json').read_text());assert len(checks['corruption_rejections'])==13
    portable=ROOT/'portable_project';assert 'ROAD_CONV_PORTABLE_PROJECT_RECREATION_PASS' in (portable/'recreate_console.log').read_text(errors='replace')
    assets=json.loads((portable/'assets.json').read_text())['files_sha256']
    for n,digest in assets.items():assert sha(portable/n)==digest
    old=json.loads((ROOT/'prj/road_conv.srcs/sources_1/bd/system/system.bd').read_text())['design']
    new=json.loads((portable/'prj/road_conv_portable.srcs/sources_1/bd/system/system.bd').read_text())['design']
    for key in ['interface_ports','ports','addressing']:
        assert old[key]==new[key],key
    for key in ['interface_nets','nets']:
        canonical=lambda group:{n:{k:sorted(v) if isinstance(v,list) else v for k,v in d.items()} for n,d in group.items()}
        assert canonical(old[key])==canonical(new[key]),key
    assert set(old['components'])==set(new['components'])
    parameter_serialization_differences={}
    for name,component in old['components'].items():
        other=new['components'][name]
        assert component['vlnv']==other['vlnv'],name
        a=component.get('parameters',{});b=other.get('parameters',{})
        if a!=b:
            assert name=='processing_system7_0'
            differences={k:[a.get(k),b.get(k)] for k in set(a)|set(b) if a.get(k)!=b.get(k)}
            expected={'PCW_IRQ_F2P_MODE':[{'value':'DIRECT'},None],**{'PCW_S_AXI_HP%d_DATA_WIDTH'%i:[{'value':'64'},None] for i in [1,2,3]}}
            assert differences==expected
            assert a['PCW_USE_FABRIC_INTERRUPT']==b['PCW_USE_FABRIC_INTERRUPT']=={'value':'0'}
            assert all(a['PCW_USE_S_AXI_HP%d'%i]==b['PCW_USE_S_AXI_HP%d'%i]=={'value':'0'} for i in [1,2,3])
            parameter_serialization_differences[name]=differences
    receipt=dict(status='PORTABLE_RECREATION_VALIDATED_AND_BD_CONNECTIVITY_EFFECTIVE_PARAMETERS_MATCH',unused_default_serialization=parameter_serialization_differences,full_rebuild_repeated=False,hardware_access=False,assets_sha256=sha(portable/'assets.json'))
    (portable/'recreation_complete.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    for name in ['prepare_road_conv_portable.py','package_road_conv_candidate.py']:shutil.copy2(HERE/name,ROOT/'source_bundle'/name)
    doc=HERE.parents[1]/'卷积加速原型验收_20261027.md';assert doc.exists();shutil.copy2(doc,ROOT/'README_验收.md')
    files={}
    def add(p,name):
        p=Path(p);assert p.is_file(),p
        assert name not in files;files[name]=p
    for name in ['road_conv.bit','road_conv.xsa','offline_acceptance.json','offline_complete.json','protocol.json','validator_selfcheck.json','timing_acceptance.txt','timing_summary.rpt','utilization.rpt','utilization_hierarchy.rpt','drc.rpt','clock_interaction.rpt','bus_skew.rpt','system_road_conv_bd.tcl','README_验收.md','build_board.tcl','ps_config_difference.json','ps7_init_reference_comparison.txt']:
        add(ROOT/name,'board/'+name)
    for dirname in ['source_bundle','future_board_test','arm_probe/source']:
        for p in (ROOT/dirname).rglob('*'):
            if p.is_file():add(p,'board/'+p.relative_to(ROOT).as_posix())
    for name in ['road_conv_probe.elf','compile_complete.json','build.log','elf_attributes.txt']:
        p=ROOT/'arm_probe'/name
        if p.exists():add(p,'board/arm_probe/'+name)
    for name in [*assets,'assets.json','recreation_complete.json','recreate_console.log']:
        add(portable/name,'board/portable_project/'+name)
    for name in ['fixtures.json','layer_budget.json','checks_complete.json','protocol.json','YOLOv5_LICENSE']:
        add(HLS/name,'hls_evidence/'+name)
    for p in (HLS/'fixtures').rglob('*'):
        if p.is_file():add(p,'hls_evidence/fixtures/'+p.relative_to(HLS/'fixtures').as_posix())
    for pe in [4,8]:
        base=HLS/f'p{pe}'
        for name in ['checked.json','ip_complete.json','road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp','csim_r2.log','synth_r2.log','cosim_r2.log']:
            add(base/name,f'hls_evidence/p{pe}/'+name)
        for sub in ['syn/report/road_conv3_fp32_csynth.rpt','sim/report/road_conv3_fp32_cosim.rpt']:
            add(base/'conv_project/solution_100mhz'/sub,f'hls_evidence/p{pe}/'+Path(sub).name)
        ip=json.loads((base/'ip_complete.json').read_text());add(ip['archive'],f'hls_evidence/p{pe}/'+Path(ip['archive']).name)
    for p in (HLS/'arm_layout_adapter').iterdir():
        if p.is_file() and p.suffix in ['.json','.c','.bin']:add(p,'hls_evidence/arm_layout_adapter/'+p.name)
    manifest=dict(status='OFFLINE_CANDIDATE_NOT_BOARD_TESTED',hardware_access=False,sd_written=False,files={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for name,p in sorted(files.items())},note='Hardware recreation assets are relative; benchmark scripts retain this PCs E:/FPGA_Enhance_Work paths. HLS fixtures are included for inspection/recovery.')
    (ROOT/'archive_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=ROOT.parent/'road_conv_candidate_offline_20261027.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.write(ROOT/'archive_manifest.json','archive_manifest.json')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,p in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==manifest['files'][name]['sha256']
    result=dict(status='OFFLINE_ARCHIVE_CRC_AND_ALL_MEMBER_SHA256_VERIFIED',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files)+1,hardware_access=False,sd_written=False)
    (ROOT/'archive_complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
