/* Small learned car/background verifier. Detector and all box coordinates stay unchanged. */
#include "road_box_refiner.h"
#include <math.h>
static int bound(int v,int last){return v<0?0:(v>last?last:v);}
int road_patch_features(const uint8_t *bgr,const float *b,uint8_t *rgb,float meta[6]){
 int x,y,c;float cx,cy,w,h,gain;uint64_t total=0;double mean;
 if(!bgr||!b||!rgb||!meta)return 1;
 for(c=0;c<5;c++)if(!isfinite(b[c]))return 2;
 if(b[2]<=b[0]||b[3]<=b[1])return 3;
 cx=b[0]+b[2];cy=b[1]+b[3];w=fmaxf(4.f,(b[2]-b[0])*3.f);h=fmaxf(4.f,(b[3]-b[1])*3.f);
 for(y=0;y<32;y++){
  int yy=bound((int)floorf(cy+((float)y+.5f-16.f)*h/32.f),479);
  for(x=0;x<32;x++){
   int xx=bound((int)floorf(cx+((float)x+.5f-16.f)*w/32.f),799),at=(y*32+x)*3;
   const uint8_t *p=bgr+(yy*800+xx)*3;
   rgb[at]=p[2];rgb[at+1]=p[1];rgb[at+2]=p[0];total+=54U*p[2]+183U*p[1]+19U*p[0];
  }
 }
 mean=(double)total/(256.0*1024.0);gain=(float)fmin(3.0,fmax(1.0,80.0/(mean+4.0)));
 for(x=0;x<3072;x++){float v=floorf((float)rgb[x]*gain+.5f);rgb[x]=(uint8_t)(v>255.f?255.f:v);}
 meta[0]=0.f;meta[1]=(b[0]+b[2])/800.f;meta[2]=(b[1]+b[3])/480.f;
 meta[3]=(b[2]-b[0])/400.f;meta[4]=(b[3]-b[1])/240.f;meta[5]=(float)(mean/255.0);
 return 0;
}
static void conv(const float *w,const float *bias,const float *a,int ic,int ih,int iw,float *out,int oc,int oh,int ow){
 int c,y,x,j,ky,kx;
 for(c=0;c<oc;c++)for(y=0;y<oh;y++)for(x=0;x<ow;x++){
  float sum=bias[c];
  for(j=0;j<ic;j++)for(ky=0;ky<3;ky++){
   int yy=y*2+ky-1;if(yy<0||yy>=ih)continue;
   for(kx=0;kx<3;kx++){
    int xx=x*2+kx-1;if(xx<0||xx>=iw)continue;
    sum+=w[((c*ic+j)*3+ky)*3+kx]*a[(j*ih+yy)*iw+xx];
   }
  }
  out[(c*oh+y)*ow+x]=sum>0.f?sum:0.f;
 }
}
int road_box_refiner(const float *w,const uint8_t *rgb,const float meta[6],float *work,float output[5]){
 float *a=work,*b,*c,*d,*f,sum;int i,j,k;
 if(!w||!rgb||!meta||!work||!output)return 1;
 b=a+3072;c=b+2048;d=c+1024;f=d+384;
 for(i=0;i<1024;i++)for(j=0;j<3;j++)a[j*1024+i]=(float)rgb[i*3+j]/255.f;
 conv(w,w+216,a,3,32,32,b,8,16,16);conv(w+224,w+1376,b,8,16,16,c,16,8,8);conv(w+1392,w+4848,c,16,8,8,d,24,4,4);
 for(i=0;i<32;i++){
  sum=w[17352+i];for(j=0;j<384;j++)sum+=w[4872+i*390+j]*d[j];for(j=0;j<6;j++)sum+=w[4872+i*390+384+j]*meta[j];f[i]=sum>0.f?sum:0.f;
 }
 for(k=0;k<5;k++){sum=w[17544+k];for(i=0;i<32;i++)sum+=w[17384+k*32+i]*f[i];output[k]=sum;}
 return 0;
}
