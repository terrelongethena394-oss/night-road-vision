#include "road_camera.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
 uint8_t *a=malloc(RC_FRAME_BYTES);uint32_t *b=malloc(RC_RAW_BYTES);FILE *f;
 if(argc!=3||!a||!b)return 2;
 f=fopen(argv[1],"rb");if(!f)return 3;if(fread(a,1,RC_FRAME_BYTES,f)!=RC_FRAME_BYTES||fgetc(f)!=EOF)return 4;fclose(f);
 road_camera_average(a,b);f=fopen(argv[2],"wb");if(!f)return 5;if(fwrite(b,1,RC_RAW_BYTES,f)!=RC_RAW_BYTES)return 6;fclose(f);
 free(a);free(b);puts("ROAD_CAMERA_AVERAGE_DONE");return 0;
}
