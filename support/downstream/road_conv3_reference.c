#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
static int load(const char *p,float *v,size_t n){FILE *f=fopen(p,"rb");int ok;if(!f)return 0;ok=fread(v,4,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 int h,w,ic,oc,s,oh,ow,y,x,o,ky,kx,c;float *a,*weights,*bias,*out;FILE *f;clock_t start;
 if(argc!=10&&argc!=11)return 2;
 h=atoi(argv[1]);w=atoi(argv[2]);ic=atoi(argv[3]);oc=atoi(argv[4]);s=atoi(argv[5]);
 if(h<1||w<1||ic<1||oc<1||(s!=1&&s!=2))return 3;
 oh=(h+s-1)/s;ow=(w+s-1)/s;
 a=malloc((size_t)h*w*ic*4);weights=malloc((size_t)9*ic*oc*4);bias=malloc(oc*4);out=malloc((size_t)oh*ow*oc*4);
 if(!a||!weights||!bias||!out)return 4;
 if(!load(argv[6],a,(size_t)h*w*ic)||!load(argv[7],weights,(size_t)9*ic*oc)||!load(argv[8],bias,oc))return 5;
 start=clock();
 for(y=0;y<oh;y++)for(x=0;x<ow;x++)for(o=0;o<oc;o++){
  float sum=bias[o];
  for(ky=0;ky<3;ky++)for(kx=0;kx<3;kx++){
   int iy=y*s+ky-1,ix=x*s+kx-1;
   if(iy<0||iy>=h||ix<0||ix>=w)continue;
   for(c=0;c<ic;c++){volatile float product=a[(iy*w+ix)*ic+c]*weights[((ky*3+kx)*ic+c)*oc+o];sum=sum+product;}
  }
  out[(y*ow+x)*oc+o]=sum;
 }
 f=fopen(argv[9],"wb");if(!f)return 6;if(fwrite(out,4,(size_t)oh*ow*oc,f)!=(size_t)oh*ow*oc)return 7;fclose(f);
 if(argc==11){
  for(c=0;c<oh*ow*oc;c++){float v=out[c],e=expf(v>=0?-v:v),sig=v>=0?1.0f/(1.0f+e):e/(1.0f+e);out[c]=v*sig;}
  f=fopen(argv[10],"wb");if(!f)return 8;if(fwrite(out,4,(size_t)oh*ow*oc,f)!=(size_t)oh*ow*oc)return 9;fclose(f);
 }
 printf("SCALAR_FP32_SINGLE_CONV_REFERENCE_DONE %.6f\n",(double)(clock()-start)/CLOCKS_PER_SEC);
 free(a);free(weights);free(bias);free(out);return 0;
}
