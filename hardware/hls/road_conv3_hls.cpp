#include "road_conv3_hls.h"
static float bits_float(ap_uint<32> bits){union {unsigned u;float f;} v;v.u=bits.to_uint();return v.f;}
static ap_uint<32> float_bits(float f){union {unsigned u;float f;} v;v.f=f;return v.u;}
template<int Lane> static float fp_mul(float a,float b){
#pragma HLS INLINE off
#pragma HLS PIPELINE II=1
 float product=a*b;
#pragma HLS RESOURCE variable=product core=FMul_fulldsp
 return product;
}
template<int Lane> static float fp_add(float a,float b){
#pragma HLS INLINE off
#pragma HLS PIPELINE II=1
 float sum=a+b;
#pragma HLS RESOURCE variable=sum core=FAddSub_fulldsp
 return sum;
}
int road_conv3_fp32(const float *input,const RoadWord *weights_mem,RoadWord *output,int height,int width,int ic4,int oc4,int stride,int kernel){
#pragma HLS INTERFACE m_axi port=input offset=slave bundle=gmem_in depth=3276800 max_read_burst_length=64 num_read_outstanding=2
#if RC_PE>=8
#pragma HLS INTERFACE m_axi port=weights_mem offset=slave bundle=gmem_w depth=18448 max_read_burst_length=64 num_read_outstanding=2
#pragma HLS INTERFACE m_axi port=output offset=slave bundle=gmem_out depth=102400 max_write_burst_length=16 num_write_outstanding=2
#else
#pragma HLS INTERFACE m_axi port=weights_mem offset=slave bundle=gmem_w depth=73792 max_read_burst_length=64 num_read_outstanding=2
#pragma HLS INTERFACE m_axi port=output offset=slave bundle=gmem_out depth=409600 max_write_burst_length=16 num_write_outstanding=2
#endif
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=weights_mem bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=ic4 bundle=control
#pragma HLS INTERFACE s_axilite port=oc4 bundle=control
#pragma HLS INTERFACE s_axilite port=stride bundle=control
#pragma HLS INTERFACE s_axilite port=kernel bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
 if((kernel!=1&&kernel!=3)||(kernel==1&&stride!=1)||height<1||height>160||width<1||width>160||ic4<4||ic4>(kernel==1?512:128)||ic4%4||oc4<RC_PE||oc4>256||oc4%RC_PE||(stride!=1&&stride!=2))return 1;
 int oh=stride==2?(height+1)/2:height,ow=stride==2?(width+1)/2:width;
 if(oh>80||ow>80)return 2;
 float patch[3*RC_PATCH*RC_MAX_IC];
#pragma HLS RESOURCE variable=patch core=RAM_2P_BRAM
 float weights[9*RC_MAX_IC][RC_PE];
#pragma HLS ARRAY_PARTITION variable=weights complete dim=2
#pragma HLS RESOURCE variable=weights core=RAM_2P_BRAM
 float acc[RC_TILE][RC_PE];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=2
#pragma HLS RESOURCE variable=acc core=RAM_2P_LUTRAM
 float bias[RC_PE];
#pragma HLS ARRAY_PARTITION variable=bias complete
 const int red=kernel*kernel*ic4,blocks=oc4/RC_PE;
 ROW:for(int y=0;y<oh;y++){
#pragma HLS LOOP_TRIPCOUNT min=1 max=80 avg=40
  TILE:for(int x0=0;x0<ow;x0+=RC_TILE){
#pragma HLS LOOP_TRIPCOUNT min=1 max=5 avg=3
   int valid=ow-x0;if(valid>RC_TILE)valid=RC_TILE;
   int cols=(stride==2?2*(valid-1):valid-1)+kernel;
   int y0=(stride==2?2*y:y)-(kernel/2),xbegin=(stride==2?2*x0:x0)-(kernel/2);
   PATCH_ROW:for(int ky=0;ky<kernel;ky++){
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
#pragma HLS LOOP_TRIPCOUNT min=4 max=8192 avg=1024
      patch[ky*RC_PATCH*RC_MAX_IC+offset+r]=input[rowbase+r];
     }
     LEFT_ZERO:for(int r=0;r<offset;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=128 avg=4
      patch[ky*RC_PATCH*RC_MAX_IC+r]=0.0f;
     }
     RIGHT_ZERO:for(int r=offset+nvalid;r<cols*ic4;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=128 avg=4
      patch[ky*RC_PATCH*RC_MAX_IC+r]=0.0f;
     }
    }else{
     ZERO_ROW:for(int r=0;r<cols*ic4;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=12 max=8192 avg=1024
      patch[ky*RC_PATCH*RC_MAX_IC+r]=0.0f;
     }
    }
   }
   int word_base=0;
   OUTPUT_BLOCK:for(int block=0;block<blocks;block++){
#pragma HLS LOOP_TRIPCOUNT min=1 max=64 avg=16
    RoadWord b=weights_mem[word_base];
    for(int o=0;o<RC_PE;o++){
#pragma HLS UNROLL
     bias[o]=bits_float(b.range(32*o+31,32*o));
    }
    LOAD_WEIGHT:for(int r=0;r<red;r++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=36 max=1152 avg=576
     RoadWord w=weights_mem[word_base+1+r];
     for(int o=0;o<RC_PE;o++){
#pragma HLS UNROLL
      weights[r][o]=bits_float(w.range(32*o+31,32*o));
     }
    }
    INIT_ACC:for(int p=0;p<RC_TILE;p++){
#pragma HLS PIPELINE II=1
     for(int o=0;o<RC_PE;o++){
#pragma HLS UNROLL
      acc[p][o]=bias[o];
     }
    }
    int ky=0,kx=0,ic=0;
    MAC_INTERLEAVED:for(int step=0;step<red*RC_TILE;step++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=576 max=18432 avg=9216
#pragma HLS DEPENDENCE variable=acc inter RAW distance=16 true
     int p=step&15,r=step>>4,col=(stride==2?2*p:p)+kx;
     float a=p<valid?patch[ky*RC_PATCH*RC_MAX_IC+col*ic4+ic]:0.0f;
     acc[p][0]=fp_add<0>(acc[p][0],fp_mul<0>(a,weights[r][0]));
     acc[p][1]=fp_add<1>(acc[p][1],fp_mul<1>(a,weights[r][1]));
     acc[p][2]=fp_add<2>(acc[p][2],fp_mul<2>(a,weights[r][2]));
     acc[p][3]=fp_add<3>(acc[p][3],fp_mul<3>(a,weights[r][3]));
#if RC_PE>=8
     acc[p][4]=fp_add<4>(acc[p][4],fp_mul<4>(a,weights[r][4]));
     acc[p][5]=fp_add<5>(acc[p][5],fp_mul<5>(a,weights[r][5]));
     acc[p][6]=fp_add<6>(acc[p][6],fp_mul<6>(a,weights[r][6]));
     acc[p][7]=fp_add<7>(acc[p][7],fp_mul<7>(a,weights[r][7]));
#if RC_PE==16
     acc[p][8]=fp_add<8>(acc[p][8],fp_mul<8>(a,weights[r][8]));
     acc[p][9]=fp_add<9>(acc[p][9],fp_mul<9>(a,weights[r][9]));
     acc[p][10]=fp_add<10>(acc[p][10],fp_mul<10>(a,weights[r][10]));
     acc[p][11]=fp_add<11>(acc[p][11],fp_mul<11>(a,weights[r][11]));
     acc[p][12]=fp_add<12>(acc[p][12],fp_mul<12>(a,weights[r][12]));
     acc[p][13]=fp_add<13>(acc[p][13],fp_mul<13>(a,weights[r][13]));
     acc[p][14]=fp_add<14>(acc[p][14],fp_mul<14>(a,weights[r][14]));
     acc[p][15]=fp_add<15>(acc[p][15],fp_mul<15>(a,weights[r][15]));
#endif
#endif
     if(p==15){ic++;if(ic==ic4){ic=0;kx++;if(kx==kernel){kx=0;ky++;}}}
    }
    STORE_OUTPUT:for(int p=0;p<valid;p++){
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=16 avg=12
     RoadWord v=0;
     for(int o=0;o<RC_PE;o++){
#pragma HLS UNROLL
      v.range(32*o+31,32*o)=float_bits(acc[p][o]);
     }
     output[((y*ow+x0+p)*blocks)+block]=v;
    }
    word_base+=red+1;
   }
  }
 }
 return 0;
}
