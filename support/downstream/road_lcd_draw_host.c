#include "road_lcd_draw.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv){
 uint32_t *raw;float *boxes;uint8_t *guard,*frame;FILE *f;long size;int count,status;
 if(argc!=6)return 2;
 raw=(uint32_t *)malloc(400U*240U*4U);guard=(uint8_t *)malloc(ROAD_LCD_FRAME_BYTES+128U);if(!raw||!guard)return 3;
 memset(guard,0xA5,ROAD_LCD_FRAME_BYTES+128U);frame=guard+64;
 f=fopen(argv[1],"rb");if(!f)return 4;if(fread(raw,4,400U*240U,f)!=400U*240U)return 5;fclose(f);
 f=fopen(argv[2],"rb");if(!f)return 6;fseek(f,0,SEEK_END);size=ftell(f);rewind(f);if(size<0||size%24)return 7;
 count=(int)(size/24);boxes=(float *)malloc((size_t)size+4U);if(!boxes)return 8;if(fread(boxes,1,(size_t)size,f)!=(size_t)size)return 9;fclose(f);
 status=road_lcd_draw(frame,raw,boxes,count,(unsigned)strtoul(argv[4],0,10),(unsigned)strtoul(argv[5],0,10));if(status)return 10;
 for(int i=0;i<64;i++)if(guard[i]!=0xA5||guard[64U+ROAD_LCD_FRAME_BYTES+i]!=0xA5)return 11;
 f=fopen(argv[3],"wb");if(!f)return 12;if(fwrite(frame,1,ROAD_LCD_FRAME_BYTES,f)!=ROAD_LCD_FRAME_BYTES)return 13;fclose(f);
 free(raw);free(boxes);free(guard);puts("ROAD_LCD_HOST_FRAME_RENDERED_GUARDS_PASS");return 0;
}
