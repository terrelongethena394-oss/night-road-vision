/* Exact byte input contract v2. Histogram ranks use one-based40 and745.
 * Fixed minspan32 limits amplification of flat/noisy regions. All three views
 * use the same transformation before the same frozen classifier.
 */
#ifndef DIGIT_NORMALIZATION_H
#define DIGIT_NORMALIZATION_H
#include <stdint.h>
static void digit_normalize(uint8_t gray[784]){
 uint16_t histogram[256]={0};int i,count=0,lo=-1,hi=-1,span,center,d,q,v;
 for(i=0;i<784;i++)histogram[gray[i]]++;
 for(i=0;i<256;i++){
  count+=(int)histogram[i];
  if(lo<0 && count>=40)lo=i;
  if(count>=745){hi=i;break;}
 }
 span=hi-lo;if(span<32)span=32;center=(lo+hi+1)/2;
 for(i=0;i<784;i++){
  d=(int)gray[i]-center;q=((d<0?-d:d)*192+span/2)/span;
  v=128+(d<0?-q:q);gray[i]=(uint8_t)(v<0?0:(v>255?255:v));
 }
}
#endif
