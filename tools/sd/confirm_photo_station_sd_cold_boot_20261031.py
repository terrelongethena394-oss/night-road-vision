"""Record the user's two independent SD power-cycle confirmations."""
from car_roi_delivery_common import read,write,sha
from build_photo_station_sd_20261031 import ROOT
def main():
    install=read(ROOT/'sd_write_verified.json');legacy=read(ROOT/'legacy_cleanup_verified.json')
    assert install['filesystem_unmounted'] and legacy['filesystem_unmounted'] and install['boot_sha256']==sha(ROOT/'BOOT.BIN')
    physical=dict(status='USER_CONFIRMED_TWO_SD_INDEPENDENT_COLD_STARTS',
        response='两次都能独立显示道路图、增强图和汽车框',
        instructed_conditions='Board power off before BOOT_CFG OFF/OFF, SD/camera/LCD connected, JTAG disconnected at board, independent power on; repeat power-off/on without PC download.',
        physical_sd_cold_boot_verified=True,user_reported_two_independent_power_cycles_passed=True,
        verification_method='User observation of physical standalone boots, not an automated claim of JTAG readback after reboot.',
        boot_sha256=install['boot_sha256'],sd_written=True,flash_written=False)
    write(ROOT/'physical_cold_boot_confirmation.json',physical)
    release=dict(status='ABI30_SD_RELEASE_DEPLOYED_AND_TWO_COLD_STARTS_USER_CONFIRMED',
        boot_sha256=install['boot_sha256'],boot_bytes=install['boot_bytes'],
        program_elf_sha256=read(ROOT/'build_verified.json')['elf_sha256'],
        complete_sd_boot_file_readback_verified=True,physical_sd_cold_boot_verified=True,
        old_active_boot_removed=True,old_historical_backup_removed=True,
        pc_recovery_backups=[install['old_boot_backup']['pc_backup'],legacy['pc_backup']],
        sd_root_after_cleanup=legacy['root_after'],sd_written=True,flash_written=False,
        detection_mode='RAW image plus native ROI verification; enhancement for display only',
        default_power_on_view='Fixed embedded night road original/enhanced/car boxes; host photo upload remains available via JTAG')
    write(ROOT/'sd_release_verified.json',release)
    print('PHOTO_STATION_SD_TWO_COLD_STARTS_CONFIRMED',install['boot_sha256'],flush=True)
if __name__=='__main__':main()
