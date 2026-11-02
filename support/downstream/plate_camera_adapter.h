/* Complete seven-character plate OCR on the SAME three image views.
 * Legacy digit_* function names are only main-loop integration hooks.
 * Gray3072 bytes/view; signed32 logits68x24/view; CTC tokens are never truth.
 */
#include "plate_glyphs.h"
#define PLATE_GRAY 0x04E00000U
#define PLATE_SCORES 0x04E10000U
#define PLATE_TOKENS 0x04E20000U
#define PLATE_NORMALIZED 0x04E30000U
#define PLATE_LOGIT_FRACTION @FRACTION@
#ifndef PLATE_CONSISTENCY_GUARD
#define PLATE_CONSISTENCY_GUARD 0
#endif
static void plate_pool(u32 address,u8 *gray){
 const u32 *frame=(const u32 *)address;u32 y,x,dy,dx,p,sum;
 u32 rx=mail[M_D_ROIX],ry=mail[M_D_ROIY],cw=mail[M_D_ROISIZE]/96U,ch=mail[M_P_HEIGHT]/32U,count=cw*ch;
 for(y=0;y<32;y++)for(x=0;x<96;x++){
  sum=0;
  for(dy=0;dy<ch;dy++)for(dx=0;dx<cw;dx++){
   p=frame[(ry+y*ch+dy)*WIDTH+rx+x*cw+dx];
   sum+=(77U*(p&255U)+150U*((p>>8)&255U)+29U*((p>>16)&255U)+128U)>>8;
  }
  gray[y*96U+x]=(u8)((sum+count/2U)/count);
 }
}
static int plate_finish(u32 view){
 const int32_t *scores=(const int32_t *)(PLATE_SCORES+view*6528U);u8 *tokens=(u8 *)(PLATE_TOKENS+view*32U);int n;
 memset(tokens,0,32U);n=plate_decode(scores,tokens+2);tokens[0]=(u8)n;tokens[1]=(u8)plate_valid(tokens+2,n);return tokens[1];
}
static int plate_run(u32 view,u32 address){
 u8 *gray=(u8 *)(PLATE_GRAY+view*3072U);int32_t *scores=(int32_t *)(PLATE_SCORES+view*6528U);
 plate_pool(address,gray);plate_normalize(gray,(int16_t *)(PLATE_NORMALIZED+view*6144U));plate_infer(gray,scores);return plate_finish(view);
}
static void digit_raw(void){
 XTime a,b;XTime_GetTime(&a);mail[M_D_RAW]=(u32)plate_run(0,INPUT);mail[M_D_EVALS]=1;
 XTime_GetTime(&b);mail[M_D_RAW_LO]=(u32)(b-a);mail[M_D_RAW_HI]=(u32)((b-a)>>32);
}
static void digit_other(void){
 XTime a,b;u8 *gray=(u8 *)(PLATE_GRAY+6144U);int reuse=-1;
#if PLATE_CONSISTENCY_GUARD
 const u8 *raw_tokens=(const u8 *)PLATE_TOKENS,*auto_tokens=(const u8 *)(PLATE_TOKENS+64U);
 mail[M_P_FALLBACK]=0;mail[M_P_ORIGINAL_ALPHA]=mail[M_ALPHA];
#endif
 XTime_GetTime(&a);mail[M_D_NET]=(u32)plate_run(1,OUTPUT);mail[M_D_EVALS]++;
 plate_pool(FINAL,gray);plate_normalize(gray,(int16_t *)(PLATE_NORMALIZED+12288U));
 if(memcmp((const void *)(PLATE_NORMALIZED+12288U),(const void *)PLATE_NORMALIZED,6144U)==0)reuse=0;
 else if(memcmp((const void *)(PLATE_NORMALIZED+12288U),(const void *)(PLATE_NORMALIZED+6144U),6144U)==0)reuse=1;
 if(reuse>=0){
  memcpy((void *)(PLATE_SCORES+13056U),(const void *)(PLATE_SCORES+(u32)reuse*6528U),6528U);
  memcpy((void *)(PLATE_TOKENS+64U),(const void *)(PLATE_TOKENS+(u32)reuse*32U),32U);mail[M_D_AUTO]=reuse==0?mail[M_D_RAW]:mail[M_D_NET];
 }else{plate_infer(gray,(int32_t *)(PLATE_SCORES+13056U));mail[M_D_AUTO]=(u32)plate_finish(2);mail[M_D_EVALS]++;}
#if PLATE_CONSISTENCY_GUARD
 /* Preserve the candidate tensors/scores/tokens before any fallback, so an
  * independent host can audit both the decision and the final displayed view. */
 memcpy((void *)(PLATE_GRAY+9216U),(const void *)(PLATE_GRAY+6144U),3072U);
 memcpy((void *)(PLATE_NORMALIZED+18432U),(const void *)(PLATE_NORMALIZED+12288U),6144U);
 memcpy((void *)(PLATE_SCORES+19584U),(const void *)(PLATE_SCORES+13056U),6528U);
 memcpy((void *)(PLATE_TOKENS+96U),(const void *)(PLATE_TOKENS+64U),32U);
 if(raw_tokens[1] && (!auto_tokens[1] || memcmp(raw_tokens+2,auto_tokens+2,7U)!=0)){
  memcpy((void *)FINAL,(const void *)INPUT,WIDTH*HEIGHT*4U);mail[M_ALPHA]=0;mail[M_P_FALLBACK]=1;
  memcpy((void *)(PLATE_GRAY+6144U),(const void *)PLATE_GRAY,3072U);
  memcpy((void *)(PLATE_NORMALIZED+12288U),(const void *)PLATE_NORMALIZED,6144U);
  memcpy((void *)(PLATE_SCORES+13056U),(const void *)PLATE_SCORES,6528U);
  memcpy((void *)(PLATE_TOKENS+64U),(const void *)PLATE_TOKENS,32U);mail[M_D_AUTO]=mail[M_D_RAW];
 }
#endif
 XTime_GetTime(&b);mail[M_D_OTHER_LO]=(u32)(b-a);mail[M_D_OTHER_HI]=(u32)((b-a)>>32);
 mail[M_D_GRAY]=PLATE_GRAY;mail[M_D_SCORES]=PLATE_SCORES;mail[M_D_VERSION]=PLATE_CONSISTENCY_GUARD?4U:3U;mail[M_D_SEQUENCE]=mail[M_SEQUENCE]+1U;
 mail[M_P_WIDTH]=mail[M_D_ROISIZE];mail[M_P_TOKENS]=PLATE_TOKENS;mail[M_P_SCORE_FRAC]=PLATE_LOGIT_FRACTION;mail[M_P_NORMALIZED]=PLATE_NORMALIZED;
}
static void plate_character(u8 *frame,u32 at,u32 top,u32 label){
 u32 y,x;if(label>=68U)label=67U;
 for(y=0;y<24;y++)for(x=0;x<20;x++)if(PLATE_GLYPHS[label][y]&(1U<<(19U-x)))pixel(frame,at+x,top+y,0xffffffU);
}
static void digit_overlay(u8 *f){
 u32 side,x,y,c,dx,dy,at;const u8 *tokens;
 u32 rx=mail[M_D_ROIX],ry=mail[M_D_ROIY],rw=mail[M_D_ROISIZE],rh=mail[M_P_HEIGHT];
 static const u8 words[3][4]={{0,1,2,255},{4,3,11,255},{1,12,11,13}};
 for(side=0;side<2;side++){
  for(x=rx-1U;x<=rx+rw;x++){pixel(f,side*400U+x,120U+ry-1U,0x00ff00U);pixel(f,side*400U+x,120U+ry+rh,0x00ff00U);}
  for(y=ry-1U;y<=ry+rh;y++){pixel(f,side*400U+rx-1U,120U+y,0x00ff00U);pixel(f,side*400U+rx+rw,120U+y,0x00ff00U);}
 }
 for(side=0;side<3;side++){
  at=8U+side*260U;tokens=(const u8 *)(PLATE_TOKENS+side*32U);
  for(y=382;y<425;y++)for(x=at;x<at+252U;x++)pixel(f,x,y,0);
  for(c=0;c<4;c++)if(words[side][c]!=255U)
   for(y=0;y<7;y++)for(x=0;x<5;x++)if(glyphs[words[side][c]][y]&(1U<<(4U-x)))
    for(dy=0;dy<3;dy++)for(dx=0;dx<3;dx++)pixel(f,at+c*18U+x*3U+dx,390U+y*3U+dy,0xffffffU);
  if(tokens[1])for(c=0;c<7;c++)plate_character(f,at+82U+c*20U,387U,tokens[2U+c]);
  else{plate_character(f,at+82U,387U,67U);plate_character(f,at+102U,387U,67U);}
 }
}
