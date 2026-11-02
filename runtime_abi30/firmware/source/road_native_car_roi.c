/* Native160x96 BGR source crop -> RGB400x240 packed32.
 * Exact halfpixel bilinear: sourcecoord=(4*destination-3)/10.
 * Read-only source, bounded coordinates, no allocation or device I/O. */
#include <stdint.h>
int road_native_car_roi(const uint8_t *src,int x0,int y0,uint32_t *dst){
 int x,y,c;
 if(!src||!dst||x0<0||x0>640||y0<0||y0>384)return 1;
 for(y=0;y<240;y++){
  int yn=y*4-3,iy,fy,jy;
  if(yn<0)yn=0;
  if(yn>950)yn=950;
  iy=yn/10;fy=yn%10;jy=iy<95?iy+1:95;
  for(x=0;x<400;x++){
   int xn=x*4-3,ix,fx,jx;uint32_t out=0;
   if(xn<0)xn=0;
   if(xn>1590)xn=1590;
   ix=xn/10;fx=xn%10;jx=ix<159?ix+1:159;
   for(c=0;c<3;c++){
    unsigned a=src[((y0+iy)*800+x0+ix)*3+2-c],b=src[((y0+iy)*800+x0+jx)*3+2-c];
    unsigned d=src[((y0+jy)*800+x0+ix)*3+2-c],e=src[((y0+jy)*800+x0+jx)*3+2-c];
    unsigned sum=a*(unsigned)((10-fy)*(10-fx))+b*(unsigned)((10-fy)*fx)+d*(unsigned)(fy*(10-fx))+e*(unsigned)(fy*fx);
    out|=((sum+50U)/100U)<<(8*c);
   }
   dst[y*400+x]=out;
  }
 }
 return 0;
}
