"""R2: preserve FP32 arithmetic and packing; replace scalar DDR patch reads by row bursts."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_burst_hls_20261027')
OLD=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027/p8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ROOT.mkdir(exist_ok=False)
    for name in ['road_conv3_hls.h','tb_road_conv3.cpp','cases_all.txt','cases_rtl.txt']:shutil.copy2(OLD/name,ROOT/name)
    shutil.copytree(OLD/'fixtures',ROOT/'fixtures')
    shutil.copy2(OLD.parent/'fixtures.json',ROOT/'fixtures.json')
    source=(OLD/'road_conv3_hls.cpp').read_text()
    source=source.replace('float patch[3][RC_PATCH][RC_MAX_IC];','float patch[3][RC_PATCH*RC_MAX_IC];')
    start=source.index('   PATCH_ROW:');end=source.index('   int word_base=0;',start)
    patch='''   PATCH_ROW:for(int ky=0;ky<3;ky++){
#pragma HLS LOOP_FLATTEN off
    int iy=y0+ky;
    if(iy>=0 && iy<height){
     int first=xbegin<0?0:xbegin;
     int limit=xbegin+cols;if(limit>width)limit=width;
     int left=first-xbegin,nvalid=(limit-first)*ic4;
     int offset=left*ic4,rowbase=(iy*width+first)*ic4;
     PATCH_VALID:for(int r=0;r<nvalid;r++){
#pragma HLS LOOP_FLATTEN off
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=4 max=4224 avg=1024
      patch[ky][offset+r]=input[rowbase+r];
     }
     LEFT_ZERO:for(int r=0;r<offset;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=128 avg=4
      patch[ky][r]=0.0f;
     }
     RIGHT_ZERO:for(int r=offset+nvalid;r<cols*ic4;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=128 avg=4
      patch[ky][r]=0.0f;
     }
    }else{
     ZERO_ROW:for(int r=0;r<cols*ic4;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=12 max=4224 avg=1024
      patch[ky][r]=0.0f;
     }
    }
   }
'''
    source=source[:start]+patch+source[end:]
    assert source.count('patch[ky][col][ic]')==1
    source=source.replace('patch[ky][col][ic]','patch[ky][col*ic4+ic]')
    (ROOT/'road_conv3_hls.cpp').write_text(source,encoding='ascii')
    for stage in ['csim','synth','cosim','export']:
        text=(OLD/(stage+'.tcl')).read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace('-ipname road_conv3_p8','-ipname road_conv3_burst_p8')
        (ROOT/(stage+'.tcl')).write_text(text,encoding='ascii')
    (ROOT/'protocol.json').write_text(json.dumps(dict(status='R2_BURST_INPUT_CANDIDATE_NOT_TESTED',parent_cpp_sha256=sha(OLD/'road_conv3_hls.cpp'),source_sha256=sha(ROOT/'road_conv3_hls.cpp'),change='Only compact patch addressing and explicit contiguous DDR row reads, same ordered FP32 MAC, weights and AXI-lite register contract',motivation='R1 physical test all outputs exact but early layers slower; generated input adapter I_ARLEN is constant1. Optimize memory traffic before full-network integration.',hardware_access=False,sd_written=False),indent=2),encoding='utf-8')
    print('ROAD_CONV_BURST_R2_PREPARED')
if __name__=='__main__':main()
