"""Create a small project-recreation kit from the routed design's BD and checked IP."""
from pathlib import Path,PurePosixPath
import hashlib,json,shutil,zipfile
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/'portable_project';out.mkdir(exist_ok=False);repo=out/'ip_repo';repo.mkdir()
    vendor=Path('E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd')
    shutil.copytree(vendor/'ip_repo',repo/'vendor')
    proof=json.loads((HLS/'p8/ip_complete.json').read_text());archive=Path(proof['archive']);assert sha(archive)==proof['archive_sha256']
    ip=repo/'road_conv3_p8';ip.mkdir()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts
        z.extractall(ip)
    shutil.copy2(ROOT/'system_road_conv_bd.tcl',out/'system_road_conv_bd.tcl')
    shutil.copy2(vendor/'ov5640_lcd.srcs/constrs_1/new/pin.xdc',out/'pin.xdc')
    text=r'''# Offline project recreation only; no hardware access.
set root [file dirname [file normalize [info script]]]
create_project road_conv_portable $root/prj -part xc7z020clg400-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $root/ip_repo/vendor $root/ip_repo/road_conv3_p8] [current_project]
update_ip_catalog
source $root/system_road_conv_bd.tcl
validate_bd_design -force
set bd [get_files -quiet */system.bd]
if {[llength $bd]!=1} {error "Missing reconstructed BD"}
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
add_files -fileset constrs_1 $root/pin.xdc
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
write_bd_tcl -force $root/recreated_bd.tcl
puts "ROAD_CONV_PORTABLE_PROJECT_RECREATION_PASS"
close_project
exit
'''
    (out/'create_project.tcl').write_text(text,encoding='ascii')
    receipt=dict(status='PORTABLE_ASSETS_PREPARED_NOT_YET_RECREATION_TESTED',files_sha256={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()},hardware_access=False)
    (out/'assets.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('ROAD_CONV_PORTABLE_ASSETS_PREPARED',len(receipt['files_sha256']))
if __name__=='__main__':main()
