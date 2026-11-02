set root E:/FPGA_Enhance_Work/multinex_static_20261025
if {![file exists $root/multinex_static_windows.xsa]} {error "Prepare Windows XSA first"}
if {[file exists $root/vitis_ws/static_app]} {error "Preserve existing application"}
setws $root/vitis_ws
platform create -name static_platform -hw $root/multinex_static_windows.xsa -proc ps7_cortexa9_0 -os standalone -no-boot-bsp
platform generate
app create -name static_app -platform static_platform -template {Empty Application} -lang c
importsources -name static_app -path $root/app_src -linker-script
app build -name static_app
set elf $root/vitis_ws/static_app/Debug/static_app.elf
if {![file exists $elf]} {error "Static application missing"}
file copy $elf $root/multinex_static.elf
puts "MULTINEX_STATIC_ARM_BUILD_PASS bytes=[file size $elf]"
exit
