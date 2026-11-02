"""Project-local IP revision workaround and checked catalog packaging; no board access."""
from pathlib import Path
import re,shutil,subprocess,xml.etree.ElementTree as ET,zipfile
from prepare_road_conv3_hls import ROOT,HERE,read,write,sha
VIVADO=Path('E:/Xilinx/Vivado/2020.2/bin/vivado.bat')

def check(pe):
    d=ROOT/f'p{pe}';assert (d/'checked.json').exists()
    ip=d/'conv_project/solution_100mhz/impl/ip';script=ip/'run_ippack.tcl'
    archive=ip/f'fpga_user_hls_road_conv3_p{pe}_1_0.zip'
    if not archive.exists():
        text=script.read_text();old=re.search(r'^set Revision\s+"?(\d+)"?',text,re.M);assert old and int(old[1])>2147483647
        backup=ROOT/f'attempts/export_revision_p{pe}';backup.mkdir(parents=True,exist_ok=False);shutil.copy2(script,backup/'run_ippack_original.tcl')
        fixed=re.sub(r'^set Revision\s+.*$','set Revision "1"',text,count=1,flags=re.M);path=ip/'run_ippack_revisionfix.tcl';path.write_text(fixed)
        with (d/'package_console.log').open('w') as f:p=subprocess.run([str(VIVADO),'-mode','batch','-source',str(path),'-log',str(d/'package_vivado.log'),'-journal',str(d/'package_vivado.jou')],cwd=ip,stdout=f,stderr=subprocess.STDOUT)
        assert p.returncode==0 and archive.exists(),(d,p.returncode)
        write(d/'revision_fix.json',dict(original_revision=old[1],new_revision=1,scope='Generatedproject IPmetadata only; noRTL, installation orsystemclock modification',backup=str(backup)))
    tree=ET.parse(ip/'component.xml').getroot();ns={'s':'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'}
    identity={k:tree.find('s:'+k,ns).text for k in ['vendor','library','name','version']}
    assert identity==dict(vendor='fpga.user',library='hls',name=f'road_conv3_p{pe}',version='1.0')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and 'component.xml' in z.namelist()
        assert z.read('component.xml')==(ip/'component.xml').read_bytes()
    driver=ip/'drivers/road_conv3_fp32_v1_0/src/xroad_conv3_fp32_hw.h';assert driver.exists()
    write(d/'ip_complete.json',dict(status='CATALOG_IP_CSIM_AND_RTL_COSIM_VERIFIED_NOT_INTEGRATED',identity=identity,archive=str(archive),archive_sha256=sha(archive),
         component_sha256=sha(ip/'component.xml'),driver_sha256=sha(driver),source_sha256={n:sha(d/n) for n in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']},hardware_access=False))
    print('ROAD_CONV3_IP_CATALOG_VERIFIED',pe,sha(archive),flush=True)

def main():
    assert (ROOT/'checks_complete.json').exists()
    for pe in [4,8]:check(pe)
    board=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027');board.mkdir(exist_ok=False)
    shutil.copy2(HERE/'build_road_conv_board.tcl',board/'build_board.tcl')
    write(board/'protocol.json',dict(status='ISOLATED_CONVOLUTION_TEST_HARDWARE_PREPARED_NO_BOARD_ACCESS',ip=read(ROOT/'p8/ip_complete.json'),
       topology='Clone knowncamera/display sourceBD in newproject, replace oldstreamneuralIP with checkedP8 DDRconvolutionIP. Currentcamera/enhancementprojects andrunningbit untouched.',
       control_base=0x43c30000,clock_hz=100000000,part='xc7z020clg400-2',main_purpose='Future standaloneCPU-versus-PL single-layer numerical/timing probe; not fullYOLOoffload orlowlightaccuracyclaim',
       source_bd='E:/FPGA_Enhance_Work/camera_nn8_20261023/prj/camera_nn.srcs/sources_1/bd/system/system.bd',
       firmware_preserved='E:/FPGA_Enhance_Work/road_camera_20261027/road_camera.elf',hardware_downloaded=False,sd_written=False))
    print('ROAD_CONV_BOARD_PROJECT_PREPARED',flush=True)
if __name__=='__main__':main()
