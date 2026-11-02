/* Native integer implementation of the frozen 26731-parameter classifier.
 * Shared by host C reference and ARM runtime, independently checked vs NumPy.
 * Q12 int16 weights; Q20 int32 biases. Proven int32 conv1/conv2/fc1, int64 fc2.
 * Input28x28 grayscale bytes. Classes0..9 and class10 trained background.
 */
#ifndef DIGIT_ARM_KERNEL_H
#define DIGIT_ARM_KERNEL_H
#include <stdint.h>
#include "cnn_weights.h"
static uint32_t digit_activation(int64_t x){
 int64_t v=x<0?-((-x+2048)>>12):((x+2048)>>12);
 return v<0?0U:(v>1048575?1048575U:(uint32_t)v);
}
static int digit_infer(const uint8_t *gray,int64_t scores[11]){
 static uint32_t p1[8][14][14],p2[16][7][7],hidden[32];
 int o,py,px,dy,dx,ky,kx,ic,i,j,sy,sx,label=0;
 int32_t acc;int64_t score,best;uint32_t z,maximum;
 for(o=0;o<8;o++)for(py=0;py<14;py++)for(px=0;px<14;px++){
  maximum=0;
  for(dy=0;dy<2;dy++)for(dx=0;dx<2;dx++){
   acc=CNN_CONV1_BIAS[o];
   for(ky=0;ky<3;ky++)for(kx=0;kx<3;kx++){
    sy=py*2+dy+ky-1;sx=px*2+dx+kx-1;
    if(sy>=0 && sy<28 && sx>=0 && sx<28)
     acc+=(int32_t)gray[sy*28+sx]*(int32_t)CNN_CONV1_WEIGHT[o][0][ky][kx];
   }
   z=digit_activation(acc);if(z>maximum)maximum=z;
  }
  p1[o][py][px]=maximum;
 }
 for(o=0;o<16;o++)for(py=0;py<7;py++)for(px=0;px<7;px++){
  maximum=0;
  for(dy=0;dy<2;dy++)for(dx=0;dx<2;dx++){
   acc=CNN_CONV2_BIAS[o];
   for(ic=0;ic<8;ic++)for(ky=0;ky<3;ky++)for(kx=0;kx<3;kx++){
    sy=py*2+dy+ky-1;sx=px*2+dx+kx-1;
    if(sy>=0 && sy<14 && sx>=0 && sx<14)
     acc+=(int32_t)p1[ic][sy][sx]*(int32_t)CNN_CONV2_WEIGHT[o][ic][ky][kx];
   }
   z=digit_activation(acc);if(z>maximum)maximum=z;
  }
  p2[o][py][px]=maximum;
 }
 for(o=0;o<32;o++){
  acc=CNN_FC1_BIAS[o];
  for(i=0;i<784;i++)acc+=(int32_t)p2[i/49][(i%49)/7][i%7]*(int32_t)CNN_FC1_WEIGHT[o][i];
  hidden[o]=digit_activation(acc);
 }
 best=INT64_MIN;
 for(i=0;i<11;i++){
  score=(int64_t)CNN_FC2_BIAS[i];
  for(j=0;j<32;j++)score+=(int64_t)hidden[j]*(int64_t)CNN_FC2_WEIGHT[i][j];
  scores[i]=score;if(score>best){best=score;label=i;}
 }
 return label;
}
#endif
