import sys
from camera_snapshot_tools import ROOT,read
import verify_camera_snapshot as verify
import package_camera_snapshot as package
def main():
 verify.main()
 if read(ROOT/'board_session.json')['status']!='ABI24_CAMERA_ONESHOT_ALL_INPUTS_AND_OUTPUTS_BOARD_VERIFIED':
  print('CAMERA_UPGRADE_NOT_VERIFIED: check board power/JTAG; no success receipt.',flush=True);return 2
 package.stage();print('CAMERA_SNAPSHOT_UPGRADE_DONE',flush=True);return 0
if __name__=='__main__':sys.exit(main())
