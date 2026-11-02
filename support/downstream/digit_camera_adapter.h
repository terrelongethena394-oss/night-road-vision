/* Included by camera main after its pixel/font/memory helpers. */
#define DIGIT_GRAY 0x04E00000U
#define DIGIT_SCORES 0x04E01000U
#define DIGIT_X 144U
#define DIGIT_Y 64U
#define DIGIT_SIZE 112U
static void digit_pool(u32 address,u8 *gray){
 const u32 *frame=(const u32 *)address;u32 y,x,dy,dx,p,sum;
 u32 rx=mail[M_D_ROIX],ry=mail[M_D_ROIY],cell=mail[M_D_ROISIZE]/28U,count=cell*cell;
 for(y=0;y<28;y++)for(x=0;x<28;x++){
  sum=0;
  for(dy=0;dy<cell;dy++)for(dx=0;dx<cell;dx++){
   p=frame[(ry+y*cell+dy)*WIDTH+rx+x*cell+dx];
   sum+=(77U*(p&255U)+150U*((p>>8)&255U)+29U*((p>>16)&255U)+128U)>>8;
  }
  gray[y*28U+x]=(u8)((sum+count/2U)/count);
 }
}
static int digit_run(u32 view,u32 address){
 u8 *gray=(u8 *)(DIGIT_GRAY+view*784U);
 int64_t *scores=(int64_t *)(DIGIT_SCORES+view*88U);
 digit_pool(address,gray);
 return digit_infer(gray,scores);
}
static void digit_raw(void){
 XTime a,b;XTime_GetTime(&a);
 mail[M_D_RAW]=(u32)digit_run(0,INPUT);mail[M_D_EVALS]=1;
 XTime_GetTime(&b);mail[M_D_RAW_LO]=(u32)(b-a);mail[M_D_RAW_HI]=(u32)((b-a)>>32);
}
static void digit_other(void){
 XTime a,b;u8 *gray=(u8 *)(DIGIT_GRAY+2U*784U);int reuse=-1;
 XTime_GetTime(&a);
 mail[M_D_NET]=(u32)digit_run(1,OUTPUT);mail[M_D_EVALS]++;
 digit_pool(FINAL,gray);
 if(memcmp(gray,(const void *)DIGIT_GRAY,784U)==0)reuse=0;
 else if(memcmp(gray,(const void *)(DIGIT_GRAY+784U),784U)==0)reuse=1;
 if(reuse>=0){
  memcpy((void *)(DIGIT_SCORES+176U),(const void *)(DIGIT_SCORES+(u32)reuse*88U),88U);
  mail[M_D_AUTO]=reuse==0?mail[M_D_RAW]:mail[M_D_NET];
 }else{
  mail[M_D_AUTO]=(u32)digit_infer(gray,(int64_t *)(DIGIT_SCORES+176U));mail[M_D_EVALS]++;
 }
 XTime_GetTime(&b);mail[M_D_OTHER_LO]=(u32)(b-a);mail[M_D_OTHER_HI]=(u32)((b-a)>>32);
 mail[M_D_GRAY]=DIGIT_GRAY;mail[M_D_SCORES]=DIGIT_SCORES;mail[M_D_VERSION]=1;
 mail[M_D_SEQUENCE]=mail[M_SEQUENCE]+1U;
}
static const u8 digit_glyph[11][7]={
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
 {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
 {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
 {14,17,17,15,1,1,14},{0,0,0,31,0,0,0}};
static void digit_overlay(u8 *f){
 u32 side,x,y,c,dx,dy,label,at;
 u32 rx=mail[M_D_ROIX],ry=mail[M_D_ROIY],size=mail[M_D_ROISIZE];
 static const u8 words[3][4]={{0,1,2,255},{4,3,11,255},{1,12,11,13}}; /* RAW NET AUTO */
 for(side=0;side<2;side++){
  for(x=rx-1U;x<=rx+size;x++){
   pixel(f,side*400U+x,120U+ry-1U,0x00ff00U);
   pixel(f,side*400U+x,120U+ry+size,0x00ff00U);
  }
  for(y=ry-1U;y<=ry+size;y++){
   pixel(f,side*400U+rx-1U,120U+y,0x00ff00U);
   pixel(f,side*400U+rx+size,120U+y,0x00ff00U);
  }
 }
 for(side=0;side<3;side++){
  at=45U+side*260U;
  for(y=385;y<420;y++)for(x=at;x<at+130U;x++)pixel(f,x,y,0);
  for(c=0;c<4;c++)if(words[side][c]!=255U)
   for(y=0;y<7;y++)for(x=0;x<5;x++)if(glyphs[words[side][c]][y]&(1U<<(4U-x)))
    for(dy=0;dy<3;dy++)for(dx=0;dx<3;dx++)pixel(f,at+c*18U+x*3U+dx,390U+y*3U+dy,0xffffffU);
  label=mail[M_D_RAW+side];if(label>10U)label=10U;
  for(y=0;y<7;y++)for(x=0;x<5;x++)if(digit_glyph[label][y]&(1U<<(4U-x)))
   for(dy=0;dy<4;dy++)for(dx=0;dx<4;dx++)pixel(f,at+90U+x*4U+dx,388U+y*4U+dy,0xffffffU);
 }
}
