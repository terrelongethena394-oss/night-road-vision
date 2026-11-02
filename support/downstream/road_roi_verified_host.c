#include "road_roi_verified.h"
#include <stdio.h>
#include <stdlib.h>
static int readall(const char *path,void *data,size_t n){FILE *f=fopen(path,"rb");int ok;if(!f)return 0;ok=fread(data,1,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 RoadRoiPolicy policy;float weights[ROAD_PERSON_WEIGHTS],input[3600],answer[1800];RoadBox full[300],roi[300],out[300];uint8_t *source;unsigned counts[2];FILE *f;int i,n;
 if(argc!=7||!readall(argv[1],&policy,sizeof(policy))||!readall(argv[2],weights,sizeof(weights)))return 2;
 source=malloc(800U*480U*3U);if(!source||!readall(argv[3],source,800U*480U*3U))return 3;
 f=fopen(argv[4],"rb");if(!f||fread(counts,4,2,f)!=2||counts[0]>300||counts[1]>300)return 4;
 n=(int)(counts[0]+counts[1]);if(fread(input,24,(size_t)n,f)!=(size_t)n||fgetc(f)!=EOF)return 5;fclose(f);
 for(i=0;i<n;i++){
  RoadBox *b=i<(int)counts[0]?full+i:roi+i-(int)counts[0];float *v=input+i*6;
  b->x1=v[0];b->y1=v[1];b->x2=v[2];b->y2=v[3];b->score=v[4];b->cls=(int)v[5];b->order=i;
 }
 n=road_roi_verified_fuse(full,(int)counts[0],roi,(int)counts[1],source,weights,&policy,strtod(argv[6],0),out,300);if(n<0)return 6;
 for(i=0;i<n;i++){float *v=answer+i*6;v[0]=out[i].x1;v[1]=out[i].y1;v[2]=out[i].x2;v[3]=out[i].y2;v[4]=out[i].score;v[5]=(float)out[i].cls;}
 f=fopen(argv[5],"wb");if(!f||fwrite(answer,24,(size_t)n,f)!=(size_t)n)return 7;fclose(f);free(source);printf("ROI_VERIFIED_NATIVE_DONE %d\n",n);return 0;
}
