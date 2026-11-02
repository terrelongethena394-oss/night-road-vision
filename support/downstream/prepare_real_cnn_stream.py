"""AXI control + stalls + auto-restart + reset for corrected video classifier."""
from pathlib import Path
import json,shutil,sys
import numpy as np
from PIL import Image
from train_real_digit_cnn import OUT,REAL

HERE=Path(__file__).resolve().parent

def main():
    revision='score64' if '--score64' in sys.argv else 'corrected'
    hlsroot=OUT/('hls_'+revision)
    dest=OUT/('rtl_stream_'+revision);dest.mkdir(exist_ok=True)
    cases=json.loads((hlsroot/'cases.json').read_text())
    manifest=json.loads((REAL/'case_manifest.json').read_text(encoding='utf-8'))
    roi=np.array(Image.open(REAL/'inputs'/(manifest['cases'][0]['id']+'.png')).convert('RGB'))[112:336,480:704]
    large=np.zeros((240,256,3),np.uint8);large[8:232,16:240]=roi
    small=np.zeros((9,17,3),np.uint8)
    for phase,(rgb,n) in enumerate([(small,3),(large,2)]):
        rgb=rgb.astype(np.uint32);values=np.tile(((rgb[:,:,0]<<16)|(rgb[:,:,1]<<8)|rgb[:,:,2]).ravel(),n)
        for kind in ('input','expected'):np.savetxt(dest/f'phase{phase}_{kind}.mem',values,fmt='%06x')
    base=Path('E:/FPGA_Enhance_Work/digit_recognition_20261023/rtl_stream/tb_digit_stream.sv')
    tb=base.read_text(encoding='ascii').replace('tb_digit_stream','tb_real_cnn_stream')
    tb=tb.replace('frames=2; mode=3;',f"frames=2; mode={cases[2]['prediction']};")
    tb=tb.replace('polls<4000','polls<100000')
    tb=tb.replace('reg [31:0] result_word;', 'reg [31:0] result_word,margin_word;')
    tb=tb.replace('            grand_total=grand_total+received;',
        "            axi_read(7'h50,margin_word);\n"+
        f"            if(margin_word!=(phase==0?{cases[0]['margin']}:{cases[2]['margin']})) $fatal(1,\"CNN margin mismatch: %d\",margin_word);\n"+
        '            grand_total=grand_total+received;')
    tb=tb.replace('DIGIT_STREAM','REAL_CNN_STREAM')
    (dest/'tb_real_cnn_stream.sv').write_text(tb,encoding='ascii')
    shutil.copy2('E:/FPGA_Enhance_Work/camera_nn8_20261023/rtl/axis_rgb_bridge.v',dest/'axis_rgb_bridge.v')
    rtl=hlsroot/'real_cnn_project/solution_100mhz/syn/verilog'
    (dest/'real_cnn_stream.prj').write_text('\n'.join('verilog xil_defaultlib "'+p.as_posix()+'"' for p in rtl.glob('*.v'))+
        '\nverilog xil_defaultlib "axis_rgb_bridge.v"\nsv xil_defaultlib "tb_real_cnn_stream.sv"\n',encoding='ascii')
    for p in rtl.glob('*.dat'):shutil.copy2(p,dest/p.name)
    run=(HERE.parent/'diagnostics/run_nn_stream_test.ps1').read_text(encoding='utf-8-sig')
    run=run.replace('E:\\FPGA_Enhance_Work\\camera_nn_20261018\\sim\\nn_full_stream',str(dest).replace('/','\\'))
    run=run.replace('nn_stream','real_cnn_stream').replace('tb_nn_stream','tb_real_cnn_stream')
    run=run.replace('NN_STREAM_AUTORESTART_BACKPRESSURE_PASS','REAL_CNN_STREAM_AUTORESTART_BACKPRESSURE_RESET_PASS')
    (dest/'run.ps1').write_text(run,encoding='ascii')
    print('REAL_CNN_NATIVE_STREAM_PREPARED',flush=True)

if __name__=='__main__':main()
