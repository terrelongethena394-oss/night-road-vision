/* Plain raster rendering shared by host verification and the ARM LCD output.
 * Input words R[7:0],G[15:8],B[23:16]; framebuffer byte order B,G,R.
 * Fonts are simple original5x7 bitmap patterns for this diagnostic interface. */
#include "road_camera.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static const uint8_t glyphs[36][7]={
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{30,1,1,14,1,1,30},
 {2,6,10,18,31,2,2},{31,16,16,30,1,1,30},{14,16,16,30,17,17,14},{31,1,2,4,8,8,8},
 {14,17,17,14,17,17,14},{14,17,17,15,1,1,14},
 {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},{30,17,17,17,17,17,30},
 {31,16,16,30,16,16,31},{31,16,16,30,16,16,16},{14,17,16,23,17,17,15},{17,17,17,31,17,17,17},
 {14,4,4,4,4,4,14},{7,2,2,2,2,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
 {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},{30,17,17,30,16,16,16},
 {14,17,17,17,21,18,13},{30,17,17,30,20,18,17},{15,16,16,14,1,1,30},{31,4,4,4,4,4,4},
 {17,17,17,17,17,17,14},{17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
 {17,17,10,4,4,4,4},{31,1,2,4,8,16,31}};
static void pixel(uint8_t *f,int x,int y,uint32_t rgb){
 if(x>=0&&x<800&&y>=0&&y<480){unsigned p=(unsigned)(y*800+x)*3U;f[p]=(uint8_t)rgb;f[p+1]=(uint8_t)(rgb>>8);f[p+2]=(uint8_t)(rgb>>16);}
}
static void fill(uint8_t *f,int x,int y,int w,int h,uint32_t rgb){int i,j;for(j=y;j<y+h;j++)for(i=x;i<x+w;i++)pixel(f,i,j,rgb);}
static void text(uint8_t *f,int x,int y,const char *s,int scale,uint32_t rgb){
 int n,r,c,dy,dx;static const uint8_t percent[7]={25,26,2,4,8,11,19};static const uint8_t period[7]={0,0,0,0,0,6,6};
 for(n=0;s[n];n++){
  const uint8_t *g=0;
  if(s[n]>='0'&&s[n]<='9')g=glyphs[s[n]-'0'];
  else if(s[n]>='A'&&s[n]<='Z')g=glyphs[10+s[n]-'A'];
  else if(s[n]=='%')g=percent;else if(s[n]=='.')g=period;
  if(g)for(r=0;r<7;r++)for(c=0;c<5;c++)if(g[r]&(1U<<(4-c)))
   for(dy=0;dy<scale;dy++)for(dx=0;dx<scale;dx++)pixel(f,x+n*6*scale+c*scale+dx,y+r*scale+dy,rgb);
 }
}
int road_camera_draw(uint8_t *f,const uint32_t *live,const uint32_t *result,const float *boxes,const float *baseline,const RoadCameraUI *u){
 static const uint32_t colors[4]={0xFFAA1E,0x00E6FF,0xDC82FF,0x3CFF6E};
 static const char *names[4]={"PERSON","CAR","TRUCK","BUS"};
 int x,y,i,k;unsigned view=0;char s[64];
 if(!f||!live||!u||u->count>300U||u->baseline_count>300U||(u->baseline_count&&!baseline)||(u->has_result&&(!result||(!boxes&&u->count))))return -1;
 view=(u->pipe_mode>>8)&1U;
 if(u->has_result)for(i=0;i<(int)u->count;i++){
  for(k=0;k<6;k++)if(!isfinite(boxes[i*6+k]))return -2;
  if(boxes[i*6+5]<0||boxes[i*6+5]>3||boxes[i*6+5]!=(float)(int)boxes[i*6+5])return -3;
 }
 if(u->has_result)for(i=0;i<(int)u->baseline_count;i++){for(k=0;k<6;k++)if(!isfinite(baseline[i*6+k]))return -2;if(baseline[i*6+5]<0||baseline[i*6+5]>3||baseline[i*6+5]!=(float)(int)baseline[i*6+5])return -3;}
 memset(f,0,RC_FRAME_BYTES);
 for(y=0;y<240;y++)for(x=0;x<400;x++){
  uint32_t v=live[y*400+x];pixel(f,x,y+100,((v&255U)<<16)|(v&0xff00U)|((v>>16)&255U));
  if(u->has_result){v=(view?live:result)[y*400+x];pixel(f,400+x,y+100,((v&255U)<<16)|(v&0xff00U)|((v>>16)&255U));}
 }
 if(u->has_result){int side;for(side=0;side<2;side++){int column=400*side;unsigned count=side||!view?u->count:u->baseline_count;const float *source=side||!view?boxes:baseline;for(i=0;i<(int)count;i++){
  const float *b=source+6*i;int cls=(int)b[5];
  int x1=(int)floorf(fmaxf(0,fminf(399,b[0]))+.5f),x2=(int)floorf(fmaxf(0,fminf(399,b[2]))+.5f);
  int y1=(int)floorf(fmaxf(0,fminf(239,b[1]))+.5f),y2=(int)floorf(fmaxf(0,fminf(239,b[3]))+.5f);
  if(x2<x1||y2<y1)return -4;
  for(x=x1;x<=x2;x++){pixel(f,column+x,100+y1,colors[cls]);pixel(f,column+x,100+y2,colors[cls]);}
  for(y=y1;y<=y2;y++){pixel(f,column+x1,100+y,colors[cls]);pixel(f,column+x2,100+y,colors[cls]);}
  if(x2-x1>=50&&y2-y1>=20){
   int tx=x1,ty=y1>=10?y1-9:y1+2,w,confidence=(int)floorf(fmaxf(0,fminf(1,b[4]))*100+.5f);
   snprintf(s,sizeof(s),"%s %d%%",names[cls],confidence);w=(int)strlen(s)*6+2;if(tx+w>400)tx=400-w;
   fill(f,column+tx,100+ty,w,9,0x081421);text(f,column+1+tx,101+ty,s,1,colors[cls]);
  }
 }}}
 text(f,10,14,view?"STABLE RAW7":"RAW IMAGE",2,0xFFFFFF);text(f,410,14,view?"ROI VERIFIED":"NEURAL ENHANCE",2,0xFFFFFF);
 if(u->busy)snprintf(s,sizeof(s),"SHOT %u PROCESSING",(unsigned)u->active_id);else if(u->has_result)snprintf(s,sizeof(s),"SHOT %u FROZEN",(unsigned)u->result_id);else strcpy(s,"LIVE PREVIEW READY");
 text(f,10,54,s,2,0xFFAA1E);
 if(u->has_result){
  snprintf(s,sizeof(s),"%s %u AGE %u MS",u->is_test?"PHOTO":"SHOT",(unsigned)u->result_id,(unsigned)u->age_ms);
  text(f,410,54,s,2,0xFFAA1E);
  snprintf(s,sizeof(s),"TEST %u MS CARS %u",(unsigned)u->detect_ms,(unsigned)u->count);text(f,410,360,s,2,0xFFFFFF);
 }else{text(f,420,180,"WAITING FOR",2,0xFFFFFF);text(f,420,212,"FIRST RESULT",2,0xFFFFFF);}
 if(u->paused)snprintf(s,sizeof(s),view?"BASE CARS %u":"CARS FROM RAW %u",(unsigned)(view?u->baseline_count:u->count));else if(u->busy)snprintf(s,sizeof(s),"DETECTING SNAP %u",(unsigned)u->active_id);else strcpy(s,"READY");
 text(f,10,360,s,2,u->paused?0xFF6666:0xFFFFFF);
 text(f,10,400,view?"SAME RAW INPUT  ROI VERIFY":"SAME CAR BOXES FROM RAW INPUT",2,0xFFFFFF);
 if(u->has_result){
  strcpy(s,view?"RAW7 VS RAW7 PLUS ROI":"LEARNED LIGHT  RAW ROI DET");
  text(f,10,440,s,2,0xFFFFFF);
 }else text(f,10,440,"RETINEX PLUS LEARNED EXPOSURE",2,0xFFFFFF);
 return 0;
}
