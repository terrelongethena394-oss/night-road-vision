set root E:/FPGA_Enhance_Work/camera_nn_digit_20261023
exec E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe $root/fix_digit_xsa_windows.py
setws $root/vitis_ws
if {[file exists $root/vitis_ws/digit_app]} {error "Preserve existing digit application; inspect before rebuilding"}
platform create -name digit_platform -hw $root/camera_digit_windows.xsa -proc ps7_cortexa9_0 -os standalone -no-boot-bsp
platform generate
app create -name digit_app -platform digit_platform -template {Empty Application} -lang c
importsources -name digit_app -path $root/app_src -linker-script
app build -name digit_app
set elf $root/vitis_ws/digit_app/Debug/digit_app.elf
if {![file exists $elf]} {error "Digit application missing"}
file copy $elf $root/camera_app.elf
puts "DIGIT_ARM_BUILD_PASS bytes=[file size $elf]"
exit
