"""Default: verify files only. --execute explicitly replaces the board's RAM app."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--readback');a=p.parse_args()
    root=Path(__file__).resolve().parent.parent
    accepted=json.loads((root/'offline_acceptance.json').read_text());assert accepted['status']=='ROUTED_TIMING_AND_SOFTWARE_CHECKED_NOT_BOARD_TESTED'
    for name,digest in accepted['artifact_sha256'].items():assert sha(root/name)==digest,'Artifact changed: '+name
    fixtures=json.loads((root/'future_board_test/fixtures.json').read_text())
    for c in fixtures:
        for key,digest in c['files_sha256'].items():assert sha(c[key])==digest,'Fixture changed: '+c['name']+'/'+key
    print('ROAD_CONV_PREFLIGHT_HASHES_PASS; board_test_executed=false',flush=True)
    if not a.execute:return
    assert a.readback,'--execute requires --readback NEW_ABSOLUTE_FOLDER'
    folder=Path(a.readback);assert folder.is_absolute() and not folder.exists()
    # This branch must only be invoked when interruption of the camera is authorized.
    tool=Path('E:/Xilinx/Vitis/2020.2/bin/xsct.bat')
    env=os.environ.copy();env['ROAD_CONV_PREFLIGHT_OK']='1'
    proc=subprocess.run([str(tool),str(root/'future_board_test/run_future_ram_test.tcl'),str(folder)],capture_output=True,text=True,env=env)
    (root/'future_board_test/last_execution.log').write_text(proc.stdout+proc.stderr,encoding='utf-8');print(proc.stdout+proc.stderr)
    assert proc.returncode==0 and 'ROAD_CONV_BOARD_READBACK_COMPLETE ' in proc.stdout,'JTAG test failed, see last_execution.log'
    subprocess.run([sys.executable,str(root/'future_board_test/validate_road_conv_board.py'),str(folder)],check=True)
if __name__=='__main__':main()
