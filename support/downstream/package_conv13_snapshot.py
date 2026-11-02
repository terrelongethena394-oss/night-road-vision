"""Package frozen synthesized RTL in a separate project while original cosim runs.
This performs offline build only. Board download remains gated on original RTL pass.
"""
import shutil,subprocess,re,zipfile,sys
from prepare_fp32_cpu_pack import BASE,read,write,sha
from prepare_road_conv13 import ROOT as HLS
from build_road_conv13 import HLS_EXE,VIVADO,route
ROOT=BASE/'road_conv13_package_20261028_r1'
PE=8
ROUTE_ON_COMPLETE=True

def main():
    if '--resume-package' in sys.argv:
        finish(ROOT/'conv_project/solution_100mhz/impl/ip')
        return
    ROOT.mkdir(exist_ok=False)
    src=HLS/'conv_project/solution_100mhz/syn/verilog'
    rtl={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
    assert rtl and 'road_conv3_fp32.v' in rtl
    shutil.copytree(HLS/'conv_project',ROOT/'conv_project',ignore=shutil.ignore_patterns('sim','csim','impl','*.log'))
    for n in ['road_conv3_hls.cpp','road_conv3_hls.h','tb_road_conv3.cpp']:shutil.copy2(HLS/n,ROOT/n)
    for p in (ROOT/'conv_project').rglob('*'):
        if p.is_file() and p.suffix in ['.app','.aps','.tcl']:
            text=p.read_text(encoding='utf-8');text=text.replace(HLS.as_posix(),ROOT.as_posix()).replace(str(HLS),str(ROOT));p.write_text(text,encoding='utf-8')
    dst=ROOT/'conv_project/solution_100mhz/syn/verilog'
    assert all(sha(dst/n)==v for n,v in rtl.items())
    write(ROOT/'copy_frozen.json',dict(status='READONLY_SYNTHESIS_SNAPSHOT_COPIED',rtl_sha256=rtl))
    script=(HLS/'export.tcl').read_text().replace(HLS.as_posix(),ROOT.as_posix())
    (ROOT/'export.tcl').write_text(script,encoding='ascii')
    with (ROOT/'export.log').open('w') as f:subprocess.run([HLS_EXE,'-f',str(ROOT/'export.tcl')],stdout=f,stderr=subprocess.STDOUT,timeout=600)
    ip=ROOT/'conv_project/solution_100mhz/impl/ip';archive=ip/f'fpga_user_hls_road_conv13_p{PE}_1_0.zip'
    if not archive.exists():
        original=(ip/'run_ippack.tcl').read_text();rev=re.search(r'^set Revision\s+"?(\d+)',original,re.M);assert rev and int(rev[1])>2147483647
        fixed=re.sub(r'^set Revision\s+.*$','set Revision "1"',original,count=1,flags=re.M);(ip/'run_ippack_revisionfix.tcl').write_text(fixed,encoding='ascii')
        with (ROOT/'package_console.log').open('w') as f:subprocess.run([VIVADO,'-mode','batch','-source',str(ip/'run_ippack_revisionfix.tcl'),'-log',str(ROOT/'package.log'),'-journal',str(ROOT/'package.jou')],cwd=ip,stdout=f,stderr=subprocess.STDOUT,timeout=600)
    assert archive.exists()
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
    assert all(sha(src/n)==v for n,v in rtl.items())
    finish(ip)

def finish(ip):
    src=HLS/'conv_project/solution_100mhz/syn/verilog';dst=ROOT/'conv_project/solution_100mhz/syn/verilog'
    rtl={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
    assert rtl=={str(p.relative_to(dst)):sha(p) for p in dst.rglob('*') if p.is_file()}
    archive=ip/f'fpga_user_hls_road_conv13_p{PE}_1_0.zip'
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and z.read('component.xml')==(ip/'component.xml').read_bytes()
    # Synthesis itself already created impl/{misc,verilog,vhdl}; only impl/ip
    # would indicate an export into the original active project.
    assert not (HLS/'conv_project/solution_100mhz/impl/ip').exists(),'Do not export into active cosim project'
    write(ROOT/'snapshot.json',dict(status='STATIC_SYNTHESIZED_RTL_SNAPSHOT_IP_PACKAGED_RTL_COSIM_PENDING',rtl_sha256=rtl,ip=str(ip),archive=str(archive),archive_sha256=sha(archive),original_project=str(HLS),initial_guard_repair='impl existed from synthesis20:17, narrowed export check toimpl/ip; original RTL hashes unchanged',sd_written=False))
    if ROUTE_ON_COMPLETE:route(ip)

if __name__=='__main__':main()
