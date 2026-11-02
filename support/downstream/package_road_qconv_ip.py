"""Export the checked R2 unit, keeping the legacy date workaround project-local."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,zipfile,xml.etree.ElementTree as ET
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_r2_schedule_20261027')
FULL=Path('E:/FPGA_Enhance_Work/road_qconv_r2_full_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    a=json.loads((ROOT/'checked.json').read_text());b=json.loads((FULL/'full_csim_checked.json').read_text())
    assert a['source_sha256']==b['source_sha256']
    for n,h in a['source_sha256'].items():assert sha(ROOT/n)==h
    script=ROOT/'export.tcl';script.write_text('cd {'+ROOT.as_posix()+'}\nopen_project qconv_project\nopen_solution solution_100mhz\nexport_design -format ip_catalog -vendor fpga.user -library hls -version 1.0 -ipname road_qconv_i8_r2\nputs "ROAD_QCONV_EXPORT_COMPLETE"\nexit\n',encoding='ascii')
    log=ROOT/'export.log';assert not log.exists()
    with log.open('w') as f:subprocess.run(['E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat','-f',str(script)],stdout=f,stderr=subprocess.STDOUT)
    ip=ROOT/'qconv_project/solution_100mhz/impl/ip';archive=ip/'fpga_user_hls_road_qconv_i8_r2_1_0.zip'
    if not archive.exists():
        source=ip/'run_ippack.tcl';text=source.read_text();old=re.search(r'^set Revision\s+"?(\d+)"?',text,re.M);assert old and int(old[1])>2147483647,log.read_text()[-5000:]
        backup=ROOT/'attempts/export_date_revision';backup.mkdir(parents=True,exist_ok=False);shutil.copy2(source,backup/'run_ippack_original.tcl')
        fixed=ip/'run_ippack_revisionfix.tcl';fixed.write_text(re.sub(r'^set Revision\s+.*$','set Revision "1"',text,count=1,flags=re.M))
        with (ROOT/'package_console.log').open('w') as f:p=subprocess.run(['E:/Xilinx/Vivado/2020.2/bin/vivado.bat','-mode','batch','-source',str(fixed),'-log',str(ROOT/'package_vivado.log'),'-journal',str(ROOT/'package_vivado.jou')],cwd=ip,stdout=f,stderr=subprocess.STDOUT)
        assert p.returncode==0 and archive.exists()
    ns={'s':'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'};tree=ET.parse(ip/'component.xml').getroot()
    identity={k:tree.find('s:'+k,ns).text for k in ['vendor','library','name','version']}
    assert identity==dict(vendor='fpga.user',library='hls',name='road_qconv_i8_r2',version='1.0')
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
    driver=ip/'drivers/road_qconv_v1_0/src/xroad_qconv_hw.h';assert driver.exists()
    (ROOT/'ip_complete.json').write_text(json.dumps(dict(status='R2_FULL_CSIM_AND_RTL_CHECKED_CATALOG_EXPORTED_NOT_BOARD_TESTED',identity=identity,archive=str(archive),archive_sha256=sha(archive),driver_sha256=sha(driver),source_sha256=a['source_sha256'],hardware_access=False),indent=2))
    print('ROAD_QCONV_CATALOG_EXPORT_PASS',flush=True)
if __name__=='__main__':main()
