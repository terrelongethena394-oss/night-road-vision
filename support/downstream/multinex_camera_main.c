/* Live camera front end for the already board-verified r4d PL enhancer.
 * Camera DMA owns a separate parked buffer. ARM switches its write park,
 * copies the completed old frame, then enhances/displays that same input.
 * No SD writes and no recognition model in this application. */
#include <stdint.h>
#include <string.h>
#include "xparameters.h"
#include "xil_types.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_mmu.h"
#include "xil_printf.h"
#include "xgpio.h"
#include "xaxivdma.h"
#include "xtime_l.h"
#include "sleep.h"
#include "display_ctrl/display_ctrl.h"
#include "vdma_api/vdma_api.h"
#include "clk_wiz/clk_wiz.h"
#include "emio_sccb_cfg/emio_sccb_cfg.h"
#include "ov5640/ov5640_init.h"
#include "xmultinex_hls_hw.h"

#define CORE 0x43C20000U
#define FRAME 0x02000000U
#define FRAME_BYTES (800U*480U*3U)
#define MAIL 0x03000000U
#define INPUT 0x04000000U
#define OUTPUT 0x04200000U
#define SCRATCH 0x04400000U
#define DIAG 0x04B00000U
#define FINAL 0x04C00000U
#define CAPTURE 0x06000000U
#define WIDTH 400U
#define HEIGHT 240U
#define MAGIC 0x4D584334U
#ifndef USE_DDR_CACHE
#define USE_DDR_CACHE 0
#endif
#ifndef NORMAL_PROTECTION
#define NORMAL_PROTECTION 0
#endif
#ifndef DIGIT_RECOGNITION
#define DIGIT_RECOGNITION 0
#endif
#if DIGIT_RECOGNITION
#include "digit_arm_kernel.h"
static void digit_raw(void);
static void digit_other(void);
static void digit_overlay(u8 *f);
#endif
#ifndef PROTECT_DARK
#define PROTECT_DARK 32U
#define PROTECT_NORMAL 48U
#endif
enum {M_MAGIC=0,M_VERSION,M_STATE,M_COMMAND,M_ACK,M_SEQUENCE,M_HEIGHT,M_WIDTH,
 M_TIMER_HZ,M_KERNEL_LO,M_KERNEL_HI,M_LOOP_LO,M_LOOP_HI,M_DMA_READ,M_DMA_WRITE,
 M_ERROR,M_HEARTBEAT,M_INPUT,M_OUTPUT,M_SCRATCH,M_DIAG,M_CAPTURE,M_DISPLAY,
 M_CURRENT,M_CAPTURE_SLOT,M_CAMERA_ID,M_LCD_ID,M_PAUSED_INPUT_HASH,M_PAUSED_OUTPUT_HASH,
 M_SNAPSHOT_LO,M_SNAPSHOT_HI,M_RENDER_LO,M_RENDER_HI,M_CACHE,
 M_LUMA,M_ALPHA,M_FINAL,M_SOURCE,
 M_D_RAW,M_D_NET,M_D_AUTO,M_D_RAW_LO,M_D_RAW_HI,M_D_OTHER_LO,M_D_OTHER_HI,
 M_D_EVALS,M_D_ROIX,M_D_ROIY,M_D_ROISIZE,M_D_GRAY,M_D_SCORES,M_D_VERSION,M_D_SEQUENCE};
static volatile u32 *const mail=(volatile u32 *)MAIL;
static XAxiVdma vdma;
static DisplayCtrl display;
static XGpio gpio;
extern u8 sccb_read_reg16(u16 reg);
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static u32 rd(u32 off){return Xil_In32(CORE+off);}
static void wr(u32 off,u32 v){Xil_Out32(CORE+off,v);}
static void ptr(u32 off,u32 a){wr(off,a);wr(off+4U,0);}
static void fatal(u32 code){
 mail[M_ERROR]=code;mail[M_STATE]=4;barrier();
 xil_printf("MULTINEX_CAMERA_ERROR %lu\r\n",(unsigned long)code);
 while(1){mail[M_HEARTBEAT]++;usleep(10000);}
}
static u32 hash(u32 address,u32 n){
 volatile u8 *p=(volatile u8 *)address;u32 h=2166136261U,i;
 for(i=0;i<n;i++)h=(h^p[i])*16777619U;
 return h;
}
static void pixel(u8 *f,u32 x,u32 y,u32 rgb){
 u32 p=(y*800U+x)*3U;f[p]=(u8)(rgb>>16);f[p+1U]=(u8)(rgb>>8);f[p+2U]=(u8)rgb;
}
static const u8 glyphs[14][7]={
 {30,17,17,30,20,18,17},{14,17,17,31,17,17,17},{17,17,17,21,21,21,10},
 {31,16,16,30,16,16,31},{17,25,25,21,19,19,17},{17,17,17,31,17,17,17},
 {17,18,20,24,20,18,17},{30,17,17,30,16,16,16},{17,27,21,21,17,17,17},
 {31,4,4,4,4,4,31},{17,17,10,4,10,17,17},
 {31,4,4,4,4,4,4},{17,17,17,17,17,17,14},{14,17,17,17,17,17,14}};
static void background(u8 *f){
 u32 a,c,y,x,dy,dx;static const u8 ids[2][3]={{0,1,2},{3,4,5}};
 memset(f,0,FRAME_BYTES);
 for(a=0;a<2;a++)for(c=0;c<3;c++)for(y=0;y<7;y++)for(x=0;x<5;x++)
  if(glyphs[ids[a][c]][y]&(1U<<(4U-x)))for(dy=0;dy<3;dy++)for(dx=0;dx<3;dx++)
   pixel(f,170U+a*400U+c*18U+x*3U+dx,16U+y*3U+dy,0xffffffU);
}
static void render(void){
 u32 slot=1U-mail[M_CURRENT],x,y,side;
 u8 *f=(u8 *)(FRAME+slot*FRAME_BYTES);
 const u32 *raw=(const u32 *)INPUT,*enh=(const u32 *)OUTPUT;
#if NORMAL_PROTECTION
 u32 c,dy,dx;const u8 keep[4]={6,3,3,7},mixed[3]={8,9,10},active[3]={3,4,5};
 const u8 *word=mail[M_ALPHA]==0?keep:(mail[M_ALPHA]==256?active:mixed);
 u32 letters=mail[M_ALPHA]==0?4U:3U;
 enh=(const u32 *)FINAL;
 for(y=10;y<42;y++)for(x=552;x<648;x++)pixel(f,x,y,0);
 for(c=0;c<letters;c++)for(y=0;y<7;y++)for(x=0;x<5;x++)
  if(glyphs[word[c]][y]&(1U<<(4U-x)))for(dy=0;dy<3;dy++)for(dx=0;dx<3;dx++)
   pixel(f,600U-letters*9U+c*18U+x*3U+dx,16U+y*3U+dy,0xffffffU);
#endif
 /* 400x240 at native resolution in each half; aspect ratio preserved. */
 for(side=0;side<2;side++)for(y=0;y<HEIGHT;y++)for(x=0;x<WIDTH;x++)
  pixel(f,side*400U+x,120U+y,side?enh[y*WIDTH+x]:raw[y*WIDTH+x]);
#if DIGIT_RECOGNITION
 digit_overlay(f);
#endif
#if USE_DDR_CACHE
 Xil_DCacheFlushRange((INTPTR)f,FRAME_BYTES);
#endif
 barrier();
 if(XAxiVdma_StartParking(&vdma,(int)slot,XAXIVDMA_READ)!=XST_SUCCESS)fatal(20);
 for(x=0;x<2000;x++){
  if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_READ)==slot){mail[M_CURRENT]=slot;return;}
  usleep(1000);
 }
 fatal(21);
}
static void capture_setup(void){
 XAxiVdma_DmaSetup cfg;UINTPTR addresses[3];unsigned i;
 memset(&cfg,0,sizeof(cfg));
 cfg.VertSizeInput=480;cfg.HoriSizeInput=800*3;cfg.Stride=800*3;
 cfg.EnableCircularBuf=0;cfg.EnableSync=0;cfg.FixedFrameStoreAddr=0;
 cfg.EnableFrameCounter=0;
 for(i=0;i<3;i++)addresses[i]=CAPTURE+i*FRAME_BYTES;
 if(XAxiVdma_DmaConfig(&vdma,XAXIVDMA_WRITE,&cfg)!=XST_SUCCESS)fatal(30);
 if(XAxiVdma_DmaSetBufferAddr(&vdma,XAXIVDMA_WRITE,addresses)!=XST_SUCCESS)fatal(31);
 if(XAxiVdma_DmaStart(&vdma,XAXIVDMA_WRITE)!=XST_SUCCESS)fatal(32);
 if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_WRITE)!=XST_SUCCESS)fatal(33);
 usleep(250000);
}
static void snapshot(void){
 u32 old=XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE),next,i,x,y,k;
 volatile u8 *source;
 u32 *dest=(u32 *)INPUT;
 if(old>1U)fatal(34);
 next=1U-old;
 if(XAxiVdma_StartParking(&vdma,(int)next,XAXIVDMA_WRITE)!=XST_SUCCESS)fatal(35);
 for(i=0;i<2000;i++){
  if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE)==next)break;
  usleep(1000);
 }
 if(i==2000)fatal(36);
 /* Let the final old-buffer AXI writes drain before CPU reads it. */
 usleep(1000);barrier();
 source=(volatile u8 *)(CAPTURE+old*FRAME_BYTES);
#if USE_DDR_CACHE
 Xil_DCacheInvalidateRange((INTPTR)source,FRAME_BYTES);
#endif
 for(y=0;y<HEIGHT;y++)for(x=0;x<WIDTH;x++){
  u32 at=(2U*y*800U+2U*x)*3U,bgr[3];
  for(k=0;k<3;k++)bgr[k]=(source[at+k]+source[at+3U+k]+
   source[at+2400U+k]+source[at+2403U+k]+2U)/4U;
  dest[y*WIDTH+x]=bgr[2]|(bgr[1]<<8)|(bgr[0]<<16);
 }
 barrier();mail[M_CAPTURE_SLOT]=old;
}
static void enhance(void){
 XTime a,b;u32 status;
 if(!(rd(0)&4U))fatal(40);
 wr(XMULTINEX_HLS_CONTROL_ADDR_H_DATA,HEIGHT);wr(XMULTINEX_HLS_CONTROL_ADDR_W_DATA,WIDTH);
 (void)rd(XMULTINEX_HLS_CONTROL_ADDR_STATUS_CTRL);
#if USE_DDR_CACHE
 Xil_DCacheFlushRange(INPUT,WIDTH*HEIGHT*4U);
 Xil_DCacheInvalidateRange(OUTPUT,WIDTH*HEIGHT*4U);
#endif
 barrier();XTime_GetTime(&a);wr(0,1U);
#if DIGIT_RECOGNITION
 digit_raw(); /* ARM RAW inference overlaps the PL enhancement job. */
#endif
 while(1){
  status=rd(0);if(status&2U)break;
  XTime_GetTime(&b);mail[M_HEARTBEAT]++;
  if(b-a>(u64)COUNTS_PER_SECOND*5U)fatal(41);
  usleep(50);
 }
 XTime_GetTime(&b);barrier();
 mail[M_KERNEL_LO]=(u32)(b-a);mail[M_KERNEL_HI]=(u32)((b-a)>>32);
#if USE_DDR_CACHE
 Xil_DCacheInvalidateRange(OUTPUT,WIDTH*HEIGHT*4U);
#endif
 if(rd(XMULTINEX_HLS_CONTROL_ADDR_STATUS_DATA)!=0U)fatal(42);
}
static void protect(void){
#if NORMAL_PROTECTION
 const u32 *a=(const u32 *)INPUT,*b=(const u32 *)OUTPUT;u32 *dest=(u32 *)FINAL;
 u32 i,p,sum=0,y,k,rb,g;
 for(i=0;i<WIDTH*HEIGHT;i++){
  p=a[i];sum+=(54U*(p&255U)+183U*((p>>8)&255U)+19U*((p>>16)&255U)+128U)>>8;
 }
 y=(sum+WIDTH*HEIGHT/2U)/(WIDTH*HEIGHT);
 k=y<=PROTECT_DARK?256U:(y>=PROTECT_NORMAL?0U:
  ((PROTECT_NORMAL-y)*256U+(PROTECT_NORMAL-PROTECT_DARK)/2U)/(PROTECT_NORMAL-PROTECT_DARK));
 if(k==0U)memcpy(dest,a,WIDTH*HEIGHT*4U);
 else if(k==256U)memcpy(dest,b,WIDTH*HEIGHT*4U);
 else for(i=0;i<WIDTH*HEIGHT;i++){
  /* Each 16-bit lane is <=255*256+128=65408: no cross-lane carry. */
  rb=(a[i]&0x00ff00ffU)*(256U-k)+(b[i]&0x00ff00ffU)*k+0x00800080U;
  g=(a[i]&0x0000ff00U)*(256U-k)+(b[i]&0x0000ff00U)*k+0x00008000U;
  dest[i]=((rb>>8)&0x00ff00ffU)|((g>>8)&0x0000ff00U);
 }
 mail[M_LUMA]=y;mail[M_ALPHA]=k;mail[M_FINAL]=FINAL;
#endif
}
#if DIGIT_RECOGNITION
#include "digit_camera_adapter.h"
#endif
int main(void){
 u32 i,injected;u16 camera;XTime start,end,snap_end,render_start;
 Xil_DCacheDisable();
#if USE_DDR_CACHE
 /* Mailbox stays noncacheable so JTAG/ARM handshakes remain coherent. */
 Xil_SetTlbAttributes(MAIL,NORM_NONCACHE);
 Xil_DCacheEnable();
#endif
 memset((void *)MAIL,0,4096);
 mail[M_CACHE]=USE_DDR_CACHE;
 mail[M_VERSION]=DIGIT_RECOGNITION?6U:(NORMAL_PROTECTION?5U:4U);mail[M_TIMER_HZ]=COUNTS_PER_SECOND;mail[M_HEIGHT]=HEIGHT;mail[M_WIDTH]=WIDTH;
 mail[M_INPUT]=INPUT;mail[M_OUTPUT]=OUTPUT;mail[M_SCRATCH]=SCRATCH;mail[M_DIAG]=DIAG;
 mail[M_CAPTURE]=CAPTURE;mail[M_DISPLAY]=FRAME;mail[M_MAGIC]=MAGIC;barrier();
 for(i=0;i<3;i++)background((u8 *)(FRAME+i*FRAME_BYTES));
#if USE_DDR_CACHE
 Xil_DCacheFlushRange(FRAME,FRAME_BYTES*3U);
#endif
 if(XGpio_Initialize(&gpio,XPAR_AXI_GPIO_0_DEVICE_ID)!=XST_SUCCESS)fatal(1);
 XGpio_SetDataDirection(&gpio,1,7);mail[M_LCD_ID]=lcd_id_read(&gpio,1);XGpio_SetDataDirection(&gpio,1,0);
 if(run_vdma_frame_buffer(&vdma,XPAR_AXIVDMA_0_DEVICE_ID,800,480,FRAME,0,0,ONLY_READ)!=XST_SUCCESS)fatal(2);
 if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_READ)!=XST_SUCCESS)fatal(3);
 clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);
 if(DisplayInitialize(&display,XPAR_VTC_0_DEVICE_ID)!=XST_SUCCESS)fatal(4);
 DisplaySetMode(&display,&VMODE_800x480);
 if(DisplayStart(&display)!=XST_SUCCESS)fatal(5);
 emio_init();camera=((u16)sccb_read_reg16(0x300a)<<8)|sccb_read_reg16(0x300b);mail[M_CAMERA_ID]=camera;
 if(camera!=0x5640 || ov5640_init(800,480,1800,1000)!=0)fatal(6);
 ptr(XMULTINEX_HLS_CONTROL_ADDR_INPUT_R_DATA,INPUT);ptr(XMULTINEX_HLS_CONTROL_ADDR_OUTPUT_R_DATA,OUTPUT);
 ptr(XMULTINEX_HLS_CONTROL_ADDR_SCRATCH_DATA,SCRATCH);ptr(XMULTINEX_HLS_CONTROL_ADDR_DIAGNOSTICS_DATA,DIAG);
 capture_setup();mail[M_STATE]=1;
 xil_printf("MULTINEX_CAMERA_READY input400x240 sensor800x480 no_sd no_recognition\r\n");
 while(1){
  if(mail[M_COMMAND]==1U){
#if NORMAL_PROTECTION && USE_DDR_CACHE
   /* FINAL is CPU-only during live display; expose it to JTAG only on pause. */
   Xil_DCacheFlushRange(FINAL,WIDTH*HEIGHT*4U);
#endif
#if DIGIT_RECOGNITION && USE_DDR_CACHE
   Xil_DCacheFlushRange(0x04E00000U,8192U);
#endif
   mail[M_PAUSED_INPUT_HASH]=hash(INPUT,WIDTH*HEIGHT*4U);
   mail[M_PAUSED_OUTPUT_HASH]=hash(OUTPUT,WIDTH*HEIGHT*4U);
   mail[M_STATE]=3;barrier();mail[M_ACK]=1;barrier();
   while(mail[M_COMMAND]==1U){mail[M_HEARTBEAT]++;usleep(1000);}
   mail[M_ACK]=0;mail[M_STATE]=1;barrier();
  }
  XTime_GetTime(&start);mail[M_STATE]=2;
  injected=NORMAL_PROTECTION && mail[M_COMMAND]==2U;
  mail[M_SOURCE]=injected;
  if(injected){
#if USE_DDR_CACHE
   Xil_DCacheInvalidateRange(INPUT,WIDTH*HEIGHT*4U);
#endif
  }else snapshot();
#if DIGIT_RECOGNITION
  if(!injected){mail[M_D_ROIX]=144;mail[M_D_ROIY]=64;mail[M_D_ROISIZE]=112;}
  if(mail[M_D_ROISIZE]<28 || mail[M_D_ROISIZE]>224 || mail[M_D_ROISIZE]%28U ||
     mail[M_D_ROIX]<1 || mail[M_D_ROIY]<1 || mail[M_D_ROIX]+mail[M_D_ROISIZE]>=WIDTH ||
     mail[M_D_ROIY]+mail[M_D_ROISIZE]>=HEIGHT)fatal(60);
#endif
  XTime_GetTime(&snap_end);enhance();protect();
#if DIGIT_RECOGNITION
  digit_other();
#endif
  XTime_GetTime(&render_start);render();
  mail[M_DMA_READ]=Xil_In32(0x43000004U)&0xff0U;
  mail[M_DMA_WRITE]=Xil_In32(0x43000034U)&0xff0U;
  if(mail[M_DMA_READ] || mail[M_DMA_WRITE])fatal(50);
  XTime_GetTime(&end);mail[M_LOOP_LO]=(u32)(end-start);mail[M_LOOP_HI]=(u32)((end-start)>>32);
  mail[M_SNAPSHOT_LO]=(u32)(snap_end-start);mail[M_SNAPSHOT_HI]=(u32)((snap_end-start)>>32);
  mail[M_RENDER_LO]=(u32)(end-render_start);mail[M_RENDER_HI]=(u32)((end-render_start)>>32);
  mail[M_SEQUENCE]++;mail[M_STATE]=1;barrier();
  if(injected){mail[M_COMMAND]=1;barrier();}
 }
}
