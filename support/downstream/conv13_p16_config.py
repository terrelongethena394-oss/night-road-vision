from prepare_fp32_cpu_pack import BASE
from prepare_conv13_p16 import ROOT as HLS,RUNTIME
PACKAGE=BASE/'road_conv13_p16_package_20261028_r1'
BOARD=BASE/'road_conv13_p16_board_20261028_r1'

def configure_build():
    import build_road_conv13 as b
    b.ROOT=BOARD;b.HLS=HLS;b.PE=16;b.SNAPSHOT=PACKAGE
    return b
