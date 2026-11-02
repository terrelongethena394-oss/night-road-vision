"""Preserve failed attempt; refresh stale XSCT read contexts once, then retry RAM test."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_burst_board_20261027')
def main():
    backup=ROOT/'attempts/first_jtag_session';backup.mkdir(parents=True,exist_ok=False)
    for name in ['future_board_test/run_future_ram_test.tcl','offline_acceptance.json','offline_complete.json']:shutil.copy2(ROOT/name,backup/Path(name).name)
    p=ROOT/'future_board_test/run_future_ram_test.tcl';text=p.read_text()
    old='proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}'
    new='''proc word {a} {
 if {[catch {mrd -value $a} value]} {
  if {![string match {*Invalid context*} $value]} {error $value}
  targets -set -filter {name =~ "ARM*#0"} -timeout 10
  set value [mrd -value $a]
 }
 return [expr {[lindex $value 0]+0}]
}'''
    assert text.count(old)==1;text=text.replace(old,new);p.write_text(text,encoding='ascii')
    for name in ['offline_acceptance.json','offline_complete.json']:
        q=ROOT/name;d=json.loads(q.read_text());d['artifact_sha256']['future_board_test/run_future_ram_test.tcl']=hashlib.sha256(p.read_bytes()).hexdigest()
        d['jtag_context_refresh']='Retry read once after ARM0 reselect only on XSCT Invalid context; prior scripts/manifests preserved in attempts/first_jtag_session'
        q.write_text(json.dumps(d,indent=2),encoding='utf-8')
    p=ROOT/'run_physical_r2_retry1.py';p.write_text((ROOT/'run_physical_r2.py').read_text().replace('_r2','_r2_retry1'),encoding='ascii')
    subprocess.run([sys.executable,str(p)],check=True)
if __name__=='__main__':main()
