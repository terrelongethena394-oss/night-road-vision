/* Plain raster rendering shared by host verification and the ARM LCD output.
 * Input words R[7:0],G[15:8],B[23:16]; framebuffer byte order B,G,R.
 * Fonts are simple original5x7 bitmap patterns for this diagnostic interface. */
#include "road_lcd_draw.h"
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
 int n,r,c,dy,dx;static const uint8_t percent[7]={25,26,2,4,8,11,19};
 for(n=0;s[n];n++){
  const uint8_t *g=0;
  if(s[n]>='0'&&s[n]<='9')g=glyphs[s[n]-'0'];
  else if(s[n]>='A'&&s[n]<='Z')g=glyphs[10+s[n]-'A'];
  else if(s[n]=='%')g=percent;
  if(g)for(r=0;r<7;r++)for(c=0;c<5;c++)if(g[r]&(1U<<(4-c)))
   for(dy=0;dy<scale;dy++)for(dx=0;dx<scale;dx++)pixel(f,x+n*6*scale+c*scale+dx,y+r*scale+dy,rgb);
 }
}
void road_lcd_waiting(uint8_t *f){
 fill(f,0,0,800,480,0x081421);text(f,220,200,"WAITING FOR IMAGE",3,0xFFFFFF);text(f,304,250,"CAMERA OFF",2,0xFFAA1E);
}
int road_lcd_draw(uint8_t *f,const uint32_t *raw,const float *boxes,int count,unsigned milliseconds,unsigned photo){
 static const uint32_t colors[4]={0xFFAA1E,0x00E6FF,0xDC82FF,0x3CFF6E};
 static const char *names[4]={"PERSON","CAR","TRUCK","BUS"};
 int x,y,i,k;char s[48];int occupied[300][4],noccupied=0;
 if(!f||!raw||count<0||count>300||(!boxes&&count))return -1;
 for(i=0;i<count;i++)for(k=0;k<6;k++)if(!isfinite(boxes[i*6+k]))return -2;
 for(y=0;y<480;y++)for(x=0;x<800;x++){
  uint32_t value=raw[(y/2)*400+x/2];unsigned p=(unsigned)(y*800+x)*3U;
  f[p]=(uint8_t)(value>>16);f[p+1]=(uint8_t)(value>>8);f[p+2]=(uint8_t)value;
 }
 for(i=0;i<count;i++){
  const float *b=boxes+i*6;int cls=(int)b[5],x1,x2,y1,y2,t;
  if(cls<0||cls>=4)return -3;
  x1=(int)floorf(fmaxf(0,fminf(799,b[0]*2))+.5f);x2=(int)floorf(fmaxf(0,fminf(799,b[2]*2))+.5f);
  y1=(int)floorf(fmaxf(0,fminf(479,b[1]*2))+.5f);y2=(int)floorf(fmaxf(0,fminf(479,b[3]*2))+.5f);
  if(x2<x1||y2<y1)return -4;
  for(t=0;t<2;t++){
   for(x=x1;x<=x2;x++){pixel(f,x,y1+t,colors[cls]);pixel(f,x,y2-t,colors[cls]);}
   for(y=y1;y<=y2;y++){pixel(f,x1+t,y,colors[cls]);pixel(f,x2-t,y,colors[cls]);}
  }
  if(x2-x1>=72&&y2-y1>=36){
   int tx=x1,ty=y1>=42?y1-11:y1+3,w,conf=(int)floorf(fmaxf(0,fminf(1,b[4]))*100+.5f),ok=1;
   snprintf(s,sizeof(s),"%s %d%%",names[cls],conf);w=(int)strlen(s)*6+4;if(tx+w>800)tx=800-w;
   for(k=0;k<noccupied;k++)if(tx<occupied[k][2]&&tx+w>occupied[k][0]&&ty<occupied[k][3]&&ty+11>occupied[k][1])ok=0;
   if(ok&&ty>=30&&ty+11<448){
    fill(f,tx,ty,w,11,0x081421);text(f,tx+2,ty+2,s,1,colors[cls]);
    occupied[noccupied][0]=tx;occupied[noccupied][1]=ty;occupied[noccupied][2]=tx+w;occupied[noccupied][3]=ty+11;noccupied++;
   }
  }
 }
 fill(f,0,0,800,30,0x081421);fill(f,0,448,800,32,0x081421);
 text(f,12,8,"STATIC ROAD TEST",2,0xFFFFFF);snprintf(s,sizeof(s),"PHOTO %02u",photo);text(f,340,8,s,2,0xFFAA1E);
 snprintf(s,sizeof(s),"BOXES %d",count);text(f,650,8,s,2,0xFFFFFF);
 snprintf(s,sizeof(s),"DETECT %u MS",milliseconds);text(f,12,457,s,2,0xFFFFFF);
 text(f,220,457,"PERSON",2,colors[0]);text(f,330,457,"CAR",2,colors[1]);text(f,414,457,"TRUCK",2,colors[2]);text(f,520,457,"BUS",2,colors[3]);
 text(f,650,457,"CAMERA OFF",2,0xFFAA1E);return 0;
}
