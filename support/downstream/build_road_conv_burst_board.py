"""Build and accept a separate R2 board candidate, then execute authorized RAM A/B test."""
from pathlib import Path
import hashlib,importlib.util,json,re,shutil,subprocess,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_burst_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name):
    s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    proof=json.loads((HLS/'checked.json').read_text());assert sha(proof['archive'])==proof['archive_sha256']
    if not (HLS/'expanded_complete.json').exists():subprocess.run([sys.executable,str(HERE/'expand_road_conv_burst_fixtures.py')],check=True)
    ROOT.mkdir(exist_ok=False)
    ip=HLS/'conv_project/solution_100mhz/impl/ip'
    driver=ip/'drivers/road_conv3_fp32_v1_0/src/xroad_conv3_fp32_hw.h'
    def registers(p):return dict(re.findall(r'^#define\s+(XROAD_CONV3_FP32_CONTROL_\w+)\s+(\w+)',p.read_text(),re.M))
    assert registers(driver)==registers(OLD/'arm_probe/source/xroad_conv3_fp32_hw.h'),'Driver ABI changed'
    script=(OLD/'build_board.tcl').read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace('E:/FPGA_Enhance_Work/road_conv_hls_20261027/p8/conv_project/solution_100mhz/impl/ip',ip.as_posix()).replace('fpga.user:hls:road_conv3_p8:1.0','fpga.user:hls:road_conv3_burst_p8:1.0')
    # Copy previously synthesized IP cache into the new checkout; never write old cache.
    cache=OLD/'prj/road_conv.cache/ip'
    shutil.copytree(cache,ROOT/'ipcache')
    create=re.search(r'^create_project .+$',script,re.M);assert create
    script=script[:create.end()]+'\nconfig_ip_cache -use_cache_location $root/ipcache'+script[create.end():]
    (ROOT/'build_board.tcl').write_text(script,encoding='ascii')
    protocol=json.loads((OLD/'protocol.json').read_text());protocol.update(status='R2_BURST_BOARD_CANDIDATE_PREPARED',ip=proof,parent_physical_results=str(OLD/'physical_readback_r1/validated.json'),hardware_downloaded=False)
    (ROOT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    for dirname in ['arm_probe','future_board_test']:
        (ROOT/dirname).mkdir()
    shutil.copytree(OLD/'arm_probe/source',ROOT/'arm_probe/source')
    for name in ['road_conv_probe.elf','compile_complete.json']:
        shutil.copy2(OLD/'arm_probe'/name,ROOT/'arm_probe'/name)
    for name in ['fixtures.json','run_future_ram_test.tcl','road_conv_preflight.py','validate_road_conv_board.py','prepared.json']:
        text=(OLD/'future_board_test'/name).read_text()
        if name=='run_future_ram_test.tcl':text=text.replace(OLD.as_posix(),ROOT.as_posix()).replace('E:/FPGA_Enhance_Work/road_conv_hls_20261027',HLS.as_posix())
        if name=='fixtures.json':text=(HLS/'future_fixtures.json').read_text()
        if name=='run_future_ram_test.tcl':
            fixtures=json.loads((HLS/'future_fixtures.json').read_text())
            entries=['{%s} {%d %d %d %d %d %d %d %d}'%(r['name'],r['h'],r['w'],r['ic4'],r['oc4'],r['stride'],r['input_fnv32'],r['packed_fnv32'],r['output_words']) for r in fixtures]
            text=re.sub(r'^set cases .*$',lambda m:'set cases [dict create '+' '.join(entries)+']',text,flags=re.M)
        (ROOT/'future_board_test'/name).write_text(text,encoding='utf-8')
    shutil.copy2('E:/FPGA_Enhance_Work/road_conv_hls_20261027/YOLOv5_LICENSE',HLS/'YOLOv5_LICENSE')
    with (ROOT/'build_console.log').open('w') as f:
        subprocess.run(['E:/Xilinx/Vivado/2020.2/bin/vivado.bat','-mode','batch','-source',str(ROOT/'build_board.tcl'),'-log',str(ROOT/'build_vivado.log'),'-journal',str(ROOT/'build_vivado.jou')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    assert 'ROAD_CONV_BOARD_OFFLINE_BUILD_PASS' in (ROOT/'build_console.log').read_text(errors='replace')
    finalize=module('finalize_road_conv_candidate');finalize.ROOT=ROOT;finalize.HLS=HLS;finalize.main()
    for name in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']:shutil.copy2(HLS/name,ROOT/'source_bundle'/name)
    shutil.copy2(HERE/'build_road_conv_burst_board.py',ROOT/'source_bundle/build_road_conv_burst_board.py')
    run=(HERE/'run_road_conv_physical.py').read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace('_r1','_r2')
    (ROOT/'run_physical_r2.py').write_text(run,encoding='ascii')
    print('ROAD_CONV_BURST_R2_ROUTED_READY_STARTING_AUTHORIZED_AB_TEST',flush=True)
    subprocess.run([sys.executable,str(ROOT/'run_physical_r2.py')],check=True)
    print('ROAD_CONV_BURST_R2_PHYSICAL_COMPLETE_CAMERA_RESTORED',flush=True)
if __name__=='__main__':main()
