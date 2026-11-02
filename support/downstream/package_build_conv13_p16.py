from conv13_p16_config import configure_build,HLS,PACKAGE,BOARD
def main():
    configure_build()
    import package_conv13_snapshot as p
    p.ROOT=PACKAGE;p.HLS=HLS;p.PE=16;p.ROUTE_ON_COMPLETE=False;p.main()
    import build_conv13_current_board as b
    b.ROOT=BOARD;b.PE=16;b.SNAPSHOT=PACKAGE;b.main()
if __name__=='__main__':main()
