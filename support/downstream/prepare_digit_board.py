"""Prepare a separate board candidate and ARM app, without touching any device."""
from pathlib import Path
import json
import re
import shutil

HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023')
BUILD=Path('E:/FPGA_Enhance_Work/camera_nn_digit_20261023')
HLS=ROOT/'hls'


def main():
    BUILD.mkdir(exist_ok=True);(BUILD/'rtl').mkdir(exist_ok=True)
    shutil.copy2(Path('E:/FPGA_Enhance_Work/camera_nn8_20261023/rtl/axis_rgb_bridge.v'),BUILD/'rtl/axis_rgb_bridge.v')
    shutil.copy2(HERE/'build_digit_board.tcl',BUILD/'build_board.tcl')
    text=(HERE.parent/'nn/fix_ip_pack_revision.py').read_text()
    text=text.replace('E:/FPGA_Enhance_Work/nanodce_fixed_20261018/hls_full_network/full_network_project',HLS.as_posix()+'/digit_project')
    text=text.replace('E:/FPGA_Enhance_Work/nanodce_fixed_20261018',ROOT.as_posix())
    (HLS/'fix_ip_revision.py').write_text(text,encoding='utf-8')
    text=(HERE.parent/'nn/check_exported_ip.tcl').read_text().replace('full_network_project','digit_project').replace('nanodce_full','digit_monitor').replace('NANODCE_IP_CATALOG_PASS','DIGIT_IP_CATALOG_PASS')
    (HLS/'check_ip.tcl').write_text(text,encoding='ascii')
    # Derive actual generated control offsets; no hand-assumed output layout.
    headers=list((HLS/'digit_project/solution_100mhz/impl/ip/drivers').glob('*/src/xdigit_monitor_hw.h'))
    if not headers:headers=list((HLS/'digit_project/solution_100mhz').rglob('xdigit_monitor_hw.h'))
    assert headers,'Export updated IP before preparing the app'
    header=headers[0].read_text()
    registers={n:int(v,16) for n,v in re.findall(r'#define\s+XDIGIT_MONITOR_CONTROL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)',header)}
    required=['HEIGHT','WIDTH','ROI_X','ROI_Y','WHICH','UI_DIGITS','PREDICTION','MARGIN','FRAME_COUNT','RESULT']
    assert all(n in registers for n in required),'Final atomic-result IP header is required'
    app=BUILD/'app_src'
    assert not app.exists(),'Preserve existing application sources'
    source=Path('E:/FPGA_Enhance_Work/camera_nn_20261018/app_src')
    shutil.copytree(source,app)
    (app/'digit_regs.h').write_text('#pragma once\n'+''.join(f'#define DIGIT_REG_{n} 0x{registers[n]:X}U\n' for n in required),encoding='ascii')
    text=(app/'main.c').read_bytes()
    anchor=b'#include "xil_io.h"'
    assert text.count(anchor)==1
    helpers=r'''
#include "digit_regs.h"
#include "sleep.h"
#define RAW_DIGIT_BASE 0x43C30000U
#define ENH_DIGIT_BASE 0x43C40000U
static int start_digit(u32 base,u32 which) {
    Xil_Out32(base+DIGIT_REG_HEIGHT,480U);
    Xil_Out32(base+DIGIT_REG_WIDTH,800U);
    Xil_Out32(base+DIGIT_REG_ROI_X,480U);
    Xil_Out32(base+DIGIT_REG_ROI_Y,112U);
    Xil_Out32(base+DIGIT_REG_WHICH,which);
    Xil_Out32(base+DIGIT_REG_UI_DIGITS,0xAAU);
    if(Xil_In32(base+DIGIT_REG_HEIGHT)!=480U || Xil_In32(base+DIGIT_REG_WIDTH)!=800U
        || Xil_In32(base+DIGIT_REG_ROI_X)!=480U || Xil_In32(base+DIGIT_REG_ROI_Y)!=112U) return 1;
    Xil_Out32(base,0x81U);
    return 0;
}
'''.encode('ascii').replace(b'\n',b'\r\n')
    text=text.replace(anchor,anchor+helpers)
    anchor=b'    /* NN control'
    assert text.count(anchor)==1
    insert=r'''
    /* Start both identical digit classifiers before the video pipeline. */
    if(start_digit(RAW_DIGIT_BASE,0U) || start_digit(ENH_DIGIT_BASE,1U)) {
        xil_printf("Digit monitor configuration failed.\r\n");
        return 1;
    }
'''.encode('ascii').replace(b'\n',b'\r\n')
    text=text.replace(anchor,insert+anchor)
    anchor=b'\tDisplayStart(&dispCtrl);'
    assert text.count(anchor)==1
    loop=r'''
    /* No recognition on ARM: each PL core publishes frame ID+label atomically.
       The pair is displayed only when both refer to the same video frame. */
    {
        u32 last=0U;
        xil_printf("DIGIT_READY ROI=(480,112) size=224; white single digit on black.\r\n");
        while(1) {
            u32 raw=Xil_In32(RAW_DIGIT_BASE+DIGIT_REG_RESULT);
            u32 enh=Xil_In32(ENH_DIGIT_BASE+DIGIT_REG_RESULT);
            u32 raw2=Xil_In32(RAW_DIGIT_BASE+DIGIT_REG_RESULT);
            u32 frame=raw>>4;
            if(raw==raw2 && frame!=0U && frame==(enh>>4) && frame!=last) {
                u32 rp=raw&15U, ep=enh&15U;
                Xil_Out32(ENH_DIGIT_BASE+DIGIT_REG_UI_DIGITS,rp|(ep<<4));
                /* UART log is evidence of classifications, not ground-truth accuracy. */
                if((frame%15U)==0U) xil_printf("DIGIT frame=%lu raw=%lu enhanced=%lu (10=blank)\r\n",
                    (unsigned long)frame,(unsigned long)rp,(unsigned long)ep);
                last=frame;
            }
            usleep(5000);
        }
    }
'''.encode('ascii').replace(b'\n',b'\r\n')
    text=text.replace(anchor,anchor+loop)
    (app/'main.c').write_bytes(text)
    (BUILD/'digit_register_map.json').write_text(json.dumps(registers,indent=2))
    print('DIGIT_BOARD_AND_ARM_SOURCES_READY',json.dumps(registers),flush=True)


if __name__=='__main__':main()
