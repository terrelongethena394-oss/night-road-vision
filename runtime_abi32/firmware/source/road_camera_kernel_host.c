#include "road_fp32.h"
#include "road_camera.h"
static unsigned calls;static volatile unsigned scratch[32];
static void preview_stub(void *p){(void)p;calls++;scratch[calls%32]^=calls;}
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
#ifndef ROAD_HOST_CONFIDENCE
#define ROAD_HOST_CONFIDENCE .25f
#endif
static int writefile(const char *name,const void *data,size_t bytes){FILE *f=fopen(name,"wb");if(!f)return -1;int ok=fwrite(data,1,bytes,f)==bytes;fclose(f);return ok?0:-1;}
static void trace(int id,const float *v,uint32_t n,void *opaque){char name[2048];snprintf(name,sizeof(name),"%s/%03d.f32",(const char *)opaque,id);if(writefile(name,v,(size_t)n*4)){fprintf(stderr,"TRACE_WRITE_FAIL\n");exit(10);}}
static int readfile(const char *name,void *data,size_t bytes){FILE *f=fopen(name,"rb");if(!f)return -1;int ok=fread(data,1,bytes,f)==bytes&&fgetc(f)==EOF;fclose(f);return ok?0:-1;}
static int boxesfile(const char *folder,const char *suffix,const RoadBox *boxes,int n){
  float values[300*6];char path[2048];int i;
  for(i=0;i<n;i++){values[i*6]=boxes[i].x1;values[i*6+1]=boxes[i].y1;values[i*6+2]=boxes[i].x2;values[i*6+3]=boxes[i].y2;values[i*6+4]=boxes[i].score;values[i*6+5]=(float)boxes[i].cls;}
  snprintf(path,sizeof(path),"%s/%s",folder,suffix);return writefile(path,values,(size_t)n*6*4);
}
int main(int argc,char **argv){
  float *weights,*arena,*decoded;uint32_t *raw;uint8_t *rgb;RoadBox *candidates,*output;clock_t start;int count,j;char path[2048];
  if(argc!=4&&argc!=5){fprintf(stderr,"weights input400.u32 outFolder [traceFolder]\n");return 2;}
  weights=(float *)malloc(ROAD_WEIGHT_FLOATS*4U);arena=(float *)calloc(ROAD_ARENA_FLOATS,4U);decoded=(float *)malloc(ROAD_CANDIDATES*9U*4U);
  raw=(uint32_t *)malloc(400U*240U*4U);rgb=(uint8_t *)malloc(320U*320U*3U);candidates=(RoadBox *)malloc(sizeof(RoadBox)*ROAD_CANDIDATES);output=(RoadBox *)malloc(sizeof(RoadBox)*300U);
  if(!weights||!arena||!decoded||!raw||!rgb||!candidates||!output)return 3;
  if(readfile(argv[1],weights,ROAD_WEIGHT_FLOATS*4U)||readfile(argv[2],raw,400U*240U*4U))return 4;
  road_preprocess400(raw,rgb);snprintf(path,sizeof(path),"%s/input320.rgb",argv[3]);if(writefile(path,rgb,320U*320U*3U))return 5;
  road_input320(rgb,arena);road_set_service(preview_stub,0);start=clock();if(road_forward(weights,arena,argc==5?trace:0,argc==5?argv[4]:0))return 6;
  road_decode(arena,decoded);for(j=0;j<ROAD_CANDIDATES*9;j++)if(!isfinite(decoded[j]))return 7;
  snprintf(path,sizeof(path),"%s/decoded.f32",argv[3]);if(writefile(path,decoded,ROAD_CANDIDATES*9U*4U))return 8;
  count=road_nms(decoded,candidates,output,300,ROAD_HOST_CONFIDENCE,.6f);if(count<0)return 9;
  if(boxesfile(argv[3],"boxes320.f32",output,count))return 11;
  road_boxes_to400(output,count);
  if(boxesfile(argv[3],"boxes400.f32",output,count))return 12;
  printf("ROAD_FP32_HOST_DONE boxes=%d cpu_seconds=%.6f\n",count,(double)(clock()-start)/CLOCKS_PER_SEC);
  printf("COOPERATIVE_CALLBACKS=%u\n",calls);if(!calls)return 16;free(weights);free(arena);free(decoded);free(raw);free(rgb);free(candidates);free(output);return 0;
}
