import sys,numpy as np
from prepare_road_sd import ROOT
from road_arm_common import read,write
import validate_road_lcd_static as validator
def main():
    raw=(ROOT.parent/'road_sd_auto_app_20261027.log').read_bytes()
    log=raw.decode('utf-16') if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else raw.decode('utf-8',errors='replace')
    assert 'ROAD_EMBEDDED_APP_AUTOSTART_PHYSICAL_READBACK_COMPLETE' in log
    flag=np.fromfile(ROOT/'auto_app_readback/auto_flag.bin','<u4');assert flag.tolist()==[0x53444231]
    validator.ROOT=ROOT;sys.argv=['validate_road_lcd_static.py',read(ROOT/'boot_image_validation.json')['first_fixture'],str(ROOT/'auto_app_readback')]
    validator.main();proof=read(ROOT/'auto_app_readback/validated.json')
    write(ROOT/'auto_app_verified.json',dict(status='EMBEDDED_WEIGHT_PHOTO_AUTOSTART_VERIFIED_ON_BOARD_WITH_NO_EXTRA_PAYLOAD_OR_TRIGGER',
         elf_sha256=proof['elf_sha256'],boxes=proof['boxes']['boxes400']['count'],frame_sha256=proof['frame_sha256'],inference_seconds=proof['inference_seconds'],
         start_method='JTAG loaded complete ELF on already configured known PL',physical_sd_cold_boot=False,sd_written=False))
    print('ROAD_EMBEDDED_AUTOSTART_NUMERIC_AND_FRAME_PASS',flush=True)
if __name__=='__main__':main()
