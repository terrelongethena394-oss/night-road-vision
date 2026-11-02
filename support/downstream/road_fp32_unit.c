#include "road_fp32.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
int main(void){
  float *d=(float *)calloc(ROAD_CANDIDATES*9U,sizeof(float));RoadBox *c=(RoadBox *)malloc(sizeof(RoadBox)*ROAD_CANDIDATES),out[10];int n;
  if(!d||!c)return 2;
  d[0]=100;d[1]=100;d[2]=20;d[3]=20;d[4]=.9f;d[5]=.9f;
  d[9]=102;d[10]=102;d[11]=20;d[12]=20;d[13]=.8f;d[14]=.9f;
  d[18]=100;d[19]=100;d[20]=20;d[21]=20;d[22]=.95f;d[24]=.9f;
  d[27]=200;d[28]=200;d[29]=20;d[30]=20;d[31]=.5f;d[32]=.5f;
  n=road_nms(d,c,out,10,.25f,.6f);
  if(n!=2||out[0].cls!=1||out[1].cls!=0)return 3;
  if(fabsf(out[0].score-.855f)>1e-6f||fabsf(out[1].score-.81f)>1e-6f)return 4;
  out[0].x1=-10;out[0].y1=40;out[0].x2=400;out[0].y2=400;road_boxes_to400(out,1);
  if(out[0].x1!=0||out[0].y1!=0||out[0].x2!=400||out[0].y2!=240)return 5;
  if(road_nms(d,c,out,0,.25f,.6f)!=0)return 6;
  free(d);free(c);puts("ROAD_FP32_NMS_AND_COORDINATE_FIXTURES_PASS");return 0;
}
