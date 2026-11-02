#include "road_camera.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int readall(const char *p,void *a,size_t n){FILE *f=fopen(p,"rb");int ok;if(!f)return 0;ok=fread(a,1,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 uint32_t *live,*result;float *boxes;uint8_t *guard,*frame;RoadCameraUI ui;FILE *f;int i;
 if(argc!=6)return 2;
 if(!readall(argv[4],&ui,sizeof(ui))||ui.count>300U)return 3;
 live=malloc(RC_RAW_BYTES);result=malloc(RC_RAW_BYTES);boxes=malloc(ui.count*24U+4U);guard=malloc(RC_FRAME_BYTES+128U);
 if(!live||!result||!boxes||!guard)return 4;
 if(!readall(argv[1],live,RC_RAW_BYTES)||!readall(argv[2],result,RC_RAW_BYTES)||!readall(argv[3],boxes,ui.count*24U))return 5;
 memset(guard,0xA5,RC_FRAME_BYTES+128U);frame=guard+64;
 if(road_camera_draw(frame,live,result,boxes,&ui))return 6;
 for(i=0;i<64;i++)if(guard[i]!=0xA5||guard[64U+RC_FRAME_BYTES+i]!=0xA5)return 7;
 f=fopen(argv[5],"wb");if(!f)return 8;if(fwrite(frame,1,RC_FRAME_BYTES,f)!=RC_FRAME_BYTES)return 9;fclose(f);
 free(live);free(result);free(boxes);free(guard);puts("ROAD_CAMERA_HOST_RENDER_GUARDS_PASS");return 0;
}
