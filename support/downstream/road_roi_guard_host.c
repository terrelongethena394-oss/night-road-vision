#include "road_roi_guard.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int readall(const char *path,void *data,size_t n){FILE *f=fopen(path,"rb");int ok;if(!f)return 0;ok=fread(data,1,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 RoadBox full[300],roi[300],out[300];float input[3600],answer[1800];RoadRoiPolicy policy;unsigned counts[2];FILE *f;int i,n;
 if(argc==4&&!strcmp(argv[1],"crop")){
  uint8_t *src=malloc(800U*480U*3U);uint32_t *dst=malloc(400U*240U*4U);
  if(!src||!dst||!readall(argv[2],src,800U*480U*3U))return 2;
  road_roi_from_bgr800(src,dst);f=fopen(argv[3],"wb");if(!f)return 3;if(fwrite(dst,4,96000,f)!=96000)return 4;fclose(f);free(src);free(dst);puts("ROI_NATIVE_CROP_PASS");return 0;
 }
 if(argc!=5||!readall(argv[1],&policy,sizeof(policy)))return 5;
 f=fopen(argv[2],"rb");if(!f||fread(counts,4,2,f)!=2||counts[0]>300||counts[1]>300)return 6;
 n=(int)(counts[0]+counts[1]);if(fread(input,24,(size_t)n,f)!=(size_t)n||fgetc(f)!=EOF)return 7;fclose(f);
 for(i=0;i<n;i++){
  RoadBox *b=i<(int)counts[0]?full+i:roi+i-(int)counts[0];float *v=input+i*6;
  b->x1=v[0];b->y1=v[1];b->x2=v[2];b->y2=v[3];b->score=v[4];b->cls=(int)v[5];b->order=i;
 }
 if(!strcmp(argv[4],"map")){n=road_roi_map400(roi,(int)counts[1]);if(n<0)return 8;memcpy(out,roi,(size_t)n*sizeof(RoadBox));}
 else {n=road_roi_fuse(full,(int)counts[0],roi,(int)counts[1],&policy,out,300);if(n<0)return 9;}
 for(i=0;i<n;i++){float *v=answer+i*6;v[0]=out[i].x1;v[1]=out[i].y1;v[2]=out[i].x2;v[3]=out[i].y2;v[4]=out[i].score;v[5]=(float)out[i].cls;}
 f=fopen(argv[3],"wb");if(!f||fwrite(answer,24,(size_t)n,f)!=(size_t)n)return 10;fclose(f);printf("ROI_NATIVE_FUSION_DONE %d\n",n);return 0;
}
