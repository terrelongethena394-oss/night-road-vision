"""Human-local one-click physical acceptance; success requires an actual receipt."""
import sys
from road_accuracy_common import ROOT,read
import verify_road_accuracy_board as verify
import report_road_accuracy as report
import package_road_accuracy as package
def main():
    verify.main()
    if read(ROOT/'board_session.json')['status']!='ABI23_FOUR_PASS_QUALITY_AND_BOARD_NUMERICS_VERIFIED':
        print('UPGRADE_NOT_DOWNLOADED_OR_NOT_VERIFIED: reconnect power/JTAG and rerun.',flush=True);return 2
    report.main();package.stage();print('ROAD_ACCURACY_UPGRADE_DONE',flush=True);return 0
if __name__=='__main__':sys.exit(main())
