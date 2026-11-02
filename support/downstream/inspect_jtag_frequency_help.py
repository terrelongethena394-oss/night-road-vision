from pathlib import Path
from prepare_road_scene_acceptance import LAB
from roi_delivery_board_tools import run
script=LAB/'jtag_frequency_help.tcl'
script.write_text('puts [help jtag frequency]\nputs [help jtag targets]\nputs JTAG_FREQUENCY_HELP_DONE\nexit 0\n',encoding='ascii')
run(script,LAB/'jtag_frequency_help.log','JTAG_FREQUENCY_HELP_DONE',timeout=35)
print((LAB/'jtag_frequency_help.log').read_text(encoding='utf-8',errors='replace')[-6500:],flush=True)
