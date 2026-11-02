"""Two targeted checks after raw-acc observation restored exact RTL results."""
from pathlib import Path
import shutil
from train_real_digit_cnn import OUT

def main():
    src=OUT/'layer_trace'
    for variant in ('relu_first','volatile_acc'):
        dst=OUT/variant;dst.mkdir(exist_ok=True)
        for name in ('cnn_weights.h','vectors.txt','tb_trace.cpp','cnn_trace.cpp','build.tcl'):
            shutil.copy2(src/name,dst/name)
        kernel=(src/'trace_kernel.h').read_text(encoding='ascii')
        if variant=='relu_first':
            start=kernel.index('static ap_uint<20> cnn_activate(');end=kernel.index('static void real_cnn_infer',start)
            kernel=kernel[:start]+'''static ap_uint<20> cnn_activate(ap_int<40> x) {
#pragma HLS INLINE
    // ReLU makes all nonpositive inputs zero, before any signed shifts.
    if(x<=0)return ap_uint<20>(0);
    ap_uint<41> positive=ap_uint<40>(x);
    positive+=2048;
    positive>>=12;
    if(positive>1048575)return ap_uint<20>(1048575);
    return ap_uint<20>(positive);
}

'''+kernel[end:]
        else:
            kernel=kernel.replace('ap_int<40> acc[4];','volatile long long acc[4];')
            kernel=kernel.replace('acc[l]+=ap_int<40>(product);','acc[l]+=product.to_int64();')
        (dst/'trace_kernel.h').write_text(kernel,encoding='ascii')
        p=dst/'tb_trace.cpp';p.write_text(p.read_text().replace(src.as_posix(),dst.as_posix()),encoding='ascii')
        print('NUMERIC_VARIANT_READY',variant,flush=True)

if __name__=='__main__':main()
