#include <stdint.h>
#include <stddef.h>
int road_zoom_pixels(const unsigned char *bgr,int x0,int y0,uint32_t *out){
 int x,y,c;
 if(!bgr||!out||x0<0||x0>520||y0<0||y0>312||(const void*)bgr==(void*)out)return 1;
 for(y=0;y<240;y++){
  int v=14*y-3,yy,fy,y1;if(v<0){v=0;}if(v>3340){v=3340;}yy=v/20;fy=v%20;y1=yy<167?yy+1:167;
  for(x=0;x<400;x++){
   int u=14*x-3,xx,fx,x1;uint32_t value=0;
   if(u<0){u=0;}if(u>5580){u=5580;}xx=u/20;fx=u%20;x1=xx<279?xx+1:279;
   for(c=0;c<3;c++){
    unsigned a=bgr[((y0+yy)*800+x0+xx)*3+2-c];
    unsigned b=bgr[((y0+yy)*800+x0+x1)*3+2-c];
    unsigned d=bgr[((y0+y1)*800+x0+xx)*3+2-c];
    unsigned e=bgr[((y0+y1)*800+x0+x1)*3+2-c];
    unsigned q=(a*(20-fx)*(20-fy)+b*fx*(20-fy)+d*(20-fx)*fy+e*fx*fy+200)/400;
    value|=q<<(8*c);
   }
   out[y*400+x]=value;
  }
 }
 return 0;
}
