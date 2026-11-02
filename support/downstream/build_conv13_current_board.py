"""Replace only the core in the currently validated camera/DDR block design."""
import shutil,subprocess
from prepare_fp32_cpu_pack import BASE,read,write,sha
from build_road_conv13 import ROOT,OLD,VIVADO,finalize
PE=8
SNAPSHOT=BASE/'road_conv13_package_20261028_r1'

def main():
    ROOT.mkdir(exist_ok=False)
    snap=read(SNAPSHOT/'snapshot.json')
    ip=snap['ip'].replace('\\','/')
    shutil.copytree(OLD/'ipcache',ROOT/'ipcache')
    script=r'''set ::env(TCL_LIBRARY) [info library]
set root ROOT
set official E:/FPGA_Enhance_Work/official_7020/ZYNQ_Vitis_7020/27_ov5640_lcd
set_param general.maxThreads 2
create_project road_conv $root/prj -part xc7z020clg400-2
config_ip_cache -use_cache_location $root/ipcache
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $official/ip_repo E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027/conv_project/solution_100mhz/impl/ip NEWIP] [current_project]
update_ip_catalog
import_files -norecurse E:/FPGA_Enhance_Work/road_conv_burst_board_20261027/prj/road_conv.srcs/sources_1/bd/system/system.bd
set bd [get_files */system.bd]
if {[llength $bd]!=1 || ![string match "$root/*" [file normalize $bd]]} {error "Isolated BD required"}
open_bd_design $bd
if {[llength [get_bd_cells -quiet road_conv_0]]!=1} {error "Expected original shared core"}
if {[get_property CONFIG.NUM_SI [get_bd_cells axi_mem_intercon]]!=5} {error "DDR topology changed"}
delete_bd_objs [get_bd_cells road_conv_0]
create_bd_cell -type ip -vlnv fpga.user:hls:road_conv13_p8:1.0 road_conv_0
connect_bd_intf_net [get_bd_intf_pins ps7_0_axi_periph/M04_AXI] [get_bd_intf_pins road_conv_0/s_axi_control]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins road_conv_0/ap_clk]
connect_bd_net [get_bd_pins rst_ps7_0_100M/peripheral_aresetn] [get_bd_pins road_conv_0/ap_rst_n]
foreach {conv_port conv_bundle} {S02 gmem_in S03 gmem_w S04 gmem_out} {
 connect_bd_intf_net [get_bd_intf_pins road_conv_0/m_axi_$conv_bundle] [get_bd_intf_pins axi_mem_intercon/${conv_port}_AXI]
}
assign_bd_address
assign_bd_address -offset 0x43C30000 -range 0x00010000 -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs road_conv_0/s_axi_control/Reg] -force
'''.replace('ROOT',ROOT.as_posix()).replace('NEWIP',ip).replace('road_conv13_p8:1.0',f'road_conv13_p{PE}:1.0')
    oldscript=(OLD/'build_board.tcl').read_text();tail=oldscript[oldscript.index('validate_bd_design -force'):]
    script+=tail
    (ROOT/'build_board.tcl').write_text(script,encoding='ascii')
    write(ROOT/'protocol.json',dict(status='CURRENT_BD_MINIMAL_CORE_REPLACEMENT',pe=PE,source_bd=str(OLD/'prj/road_conv.srcs/sources_1/bd/system/system.bd'),snapshot_sha256=sha(SNAPSHOT/'snapshot.json'),previous_failed_build=str(BASE/'road_conv13_board_20261028_r1'),hardware_downloaded=False,sd_written=False))
    with (ROOT/'build_console.log').open('w') as f:p=subprocess.run([VIVADO,'-mode','batch','-source',str(ROOT/'build_board.tcl'),'-log',str(ROOT/'build_vivado.log'),'-journal',str(ROOT/'build_vivado.jou')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
    assert p.returncode==0 and 'ROAD_CONV_BOARD_OFFLINE_BUILD_PASS' in (ROOT/'build_console.log').read_text(errors='replace')
    finalize()

if __name__=='__main__':main()
