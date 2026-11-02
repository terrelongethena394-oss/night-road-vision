// Given-ROI 28x28 CNN. All multiplications explicitly signed and widened.
// Four output channels share the input read; quantization matches Python.
#pragma once
#include <ap_int.h>
#include "cnn_weights.h"

static ap_uint<20> cnn_activate(ap_int<40> x) {
#pragma HLS INLINE
    ap_int<40> z;
    if(x<0)z=-((-x+2048)>>12);
    else z=(x+2048)>>12;
    if(z<0)z=0;
    if(z>1048575)z=1048575;
    return ap_uint<20>(z);
}

static void real_cnn_infer(ap_uint<14> sums[784],int &prediction,int &margin) {
    ap_uint<8> pixels[28][28];
    ap_uint<20> pool1[8][14][14],pool2[16][7][7],hidden[32];
#pragma HLS ARRAY_PARTITION variable=pool1 cyclic factor=4 dim=1
#pragma HLS ARRAY_PARTITION variable=pool2 cyclic factor=4 dim=1
#pragma HLS ARRAY_PARTITION variable=CNN_CONV1_WEIGHT cyclic factor=4 dim=1
#pragma HLS ARRAY_PARTITION variable=CNN_CONV2_WEIGHT cyclic factor=4 dim=1
#pragma HLS ARRAY_PARTITION variable=CNN_FC1_WEIGHT cyclic factor=4 dim=1
    for(int i=0;i<784;++i) {
#pragma HLS PIPELINE II=1
        pixels[i/28][i%28]=(ap_uint<15>(sums[i])+32)>>6;
    }
    for(int base=0;base<8;base+=4)for(int py=0;py<14;++py)for(int px=0;px<14;++px) {
        ap_uint<20> maximum[4];
#pragma HLS ARRAY_PARTITION variable=maximum complete
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            maximum[l]=0;
        }
        for(int dy=0;dy<2;++dy)for(int dx=0;dx<2;++dx) {
            // Preserve signed, ordered accumulator updates in HLS 2020.2.
            // Conservative bounds prove every sum fits signed 40 bits; the
            // native 64-bit storage avoids the failing ap_int-array lowering.
            volatile long long acc[4];
#pragma HLS ARRAY_PARTITION variable=acc complete
            for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                acc[l]=CNN_CONV1_BIAS[base+l];
            }
            for(int k=0;k<9;++k) {
#pragma HLS PIPELINE II=1
                int sy=py*2+dy+k/3-1,sx=px*2+dx+k%3-1;
                ap_int<9> value=(sy>=0&&sy<28&&sx>=0&&sx<28)?ap_int<9>(pixels[sy][sx]):ap_int<9>(0);
                for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                    ap_int<17> w=CNN_CONV1_WEIGHT[base+l][0][k/3][k%3];
                    ap_int<26> product=value*w;
#pragma HLS BIND_OP variable=product op=mul impl=dsp
                    acc[l]+=product.to_int64();
                }
            }
            for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                ap_uint<20> z=cnn_activate(acc[l]);
                if(z>maximum[l])maximum[l]=z;
            }
        }
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            pool1[base+l][py][px]=maximum[l];
        }
    }
    for(int base=0;base<16;base+=4)for(int py=0;py<7;++py)for(int px=0;px<7;++px) {
        ap_uint<20> maximum[4];
#pragma HLS ARRAY_PARTITION variable=maximum complete
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            maximum[l]=0;
        }
        for(int dy=0;dy<2;++dy)for(int dx=0;dx<2;++dx) {
            volatile long long acc[4];
#pragma HLS ARRAY_PARTITION variable=acc complete
            for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                acc[l]=CNN_CONV2_BIAS[base+l];
            }
            for(int ic=0;ic<8;++ic)for(int k=0;k<9;++k) {
#pragma HLS PIPELINE II=1
                int sy=py*2+dy+k/3-1,sx=px*2+dx+k%3-1;
                ap_int<21> value=(sy>=0&&sy<14&&sx>=0&&sx<14)?ap_int<21>(pool1[ic][sy][sx]):ap_int<21>(0);
                for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                    ap_int<17> w=CNN_CONV2_WEIGHT[base+l][ic][k/3][k%3];
                    ap_int<38> product=value*w;
#pragma HLS BIND_OP variable=product op=mul impl=dsp
                    acc[l]+=product.to_int64();
                }
            }
            for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                ap_uint<20> z=cnn_activate(acc[l]);
                if(z>maximum[l])maximum[l]=z;
            }
        }
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            pool2[base+l][py][px]=maximum[l];
        }
    }
    for(int base=0;base<32;base+=4) {
        volatile long long acc[4];
#pragma HLS ARRAY_PARTITION variable=acc complete
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            acc[l]=CNN_FC1_BIAS[base+l];
        }
        for(int i=0;i<784;++i) {
#pragma HLS PIPELINE II=1
            ap_int<21> value=pool2[i/49][(i%49)/7][i%7];
            for(int l=0;l<4;++l) {
#pragma HLS UNROLL
                ap_int<17> w=CNN_FC1_WEIGHT[base+l][i];
                ap_int<38> product=value*w;
#pragma HLS BIND_OP variable=product op=mul impl=dsp
                acc[l]+=product.to_int64();
            }
        }
        for(int l=0;l<4;++l) {
#pragma HLS UNROLL
            hidden[base+l]=cnn_activate(acc[l]);
        }
    }
    // Keep final negative biases signed through Vivado DSP inference as well.
    long long best=-(1LL<<38),second=best;
    int label=10;
    for(int k=0;k<11;++k) {
        volatile long long score=CNN_FC2_BIAS[k];
        for(int j=0;j<32;++j) {
#pragma HLS PIPELINE II=1
            ap_int<21> value=hidden[j];
            ap_int<17> w=CNN_FC2_WEIGHT[k][j];
            ap_int<38> product=value*w;
#pragma HLS BIND_OP variable=product op=mul impl=dsp
            score+=product.to_int64();
        }
        if(score>best) {second=best;best=score;label=k;}
        else if(score>second)second=score;
    }
    long long delta=best-second;
    prediction=label;
    margin=delta>2147483647?2147483647:int(delta);
}
