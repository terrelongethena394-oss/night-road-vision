/* Static-photo validation only. No camera/S2MM, SD or recognition initialization.
 * The ARM arranges buffers/display. All enhancement arithmetic runs in PL. */
#include <stdint.h>
#include <string.h>
#include "xparameters.h"
#include "xil_types.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xgpio.h"
#include "xaxivdma.h"
#include "xtime_l.h"
#include "sleep.h"
#include "display_ctrl/display_ctrl.h"
#include "vdma_api/vdma_api.h"
#include "clk_wiz/clk_wiz.h"
#include "xmultinex_hls_hw.h"

#define CORE 0x43C20000U
#define FRAME 0x02000000U
#define FRAME_BYTES (800U*480U*3U)
#define MAIL 0x03000000U
#define INPUT 0x04000000U
#define OUTPUT 0x04200000U
#define SCRATCH 0x04400000U
#define DIAG 0x04B00000U
#define MAX_PIXELS (800U*480U)
#define MAGIC 0x4D584633U
enum {M_MAGIC=0,M_VERSION,M_STATE,M_REQUEST,M_DONE,M_HEIGHT,M_WIDTH,M_TICKS_LO,M_TICKS_HI,
    M_TIMER_HZ,M_CORE_STATUS,M_INPUT_HASH,M_OUTPUT_HASH,M_DMA_ERROR,M_ERROR,M_HEARTBEAT,
    M_INPUT,M_OUTPUT,M_SCRATCH,M_DIAG,M_DISPLAY0,M_DISPLAY1,M_CURRENT,M_PROTOCOL,
    M_MAX_PIXELS,M_RGB_BYTES,M_SCRATCH_BYTES};
static volatile u32 *const mail=(volatile u32 *)MAIL;
static XAxiVdma vdma;static DisplayCtrl display;static XGpio gpio;
static void barrier(void){__asm__ volatile("dsb sy" ::: "memory");}
static u32 rd(u32 off){return Xil_In32(CORE+off);}
static void wr(u32 off,u32 v){Xil_Out32(CORE+off,v);}
static void pointer_reg(u32 off,u32 address){wr(off,address);wr(off+4U,0U);}
static u32 hash_bytes(u32 address,u32 length){
    volatile u8 *p=(volatile u8 *)address;u32 h=2166136261U,i;
    for(i=0;i<length;i++)h=(h^p[i])*16777619U;
    return h;
}
static void fail(u32 code,u32 seq){
    mail[M_ERROR]=code;mail[M_STATE]=4U;barrier();mail[M_DONE]=seq;barrier();
    xil_printf("MULTINEX_STATIC_ERROR code=%lu seq=%lu\r\n",(unsigned long)code,(unsigned long)seq);
}
static void pixel(u8 *frame,u32 x,u32 y,u32 rgb){
    u32 at=(y*800U+x)*3U;
    /* VDMA LCD path is B,G,R byte order; kernel memory is R,G,B,0. */
    frame[at]=(u8)(rgb>>16);frame[at+1U]=(u8)(rgb>>8);frame[at+2U]=(u8)rgb;
}
/* 5x7 uppercase labels, enlarged 3x. No target labels enter the FPGA model. */
static const u8 glyphs[6][7]={
 {30,17,17,30,20,18,17}, /* R */
 {14,17,17,31,17,17,17}, /* A */
 {17,17,17,21,21,21,10}, /* W */
 {31,16,16,30,16,16,31}, /* E */
 {17,25,25,21,19,19,17}, /* N */
 {17,17,17,31,17,17,17}  /* H */
};
static void labels(u8 *frame){
    unsigned word,c,y,x,dy,dx;static const u8 ids[2][3]={{0,1,2},{3,4,5}};
    for(word=0;word<2;word++)for(c=0;c<3;c++)for(y=0;y<7;y++)for(x=0;x<5;x++)
        if(glyphs[ids[word][c]][y]&(1U<<(4U-x)))for(dy=0;dy<3;dy++)for(dx=0;dx<3;dx++)
            pixel(frame,170U+word*400U+c*18U+x*3U+dx,16U+y*3U+dy,0x00ffffffU);
}
static int render(u32 h,u32 w){
    u32 current=mail[M_CURRENT],slot=1U-current,x,y,side,tw,th,x0,y0;
    u8 *frame=(u8 *)(FRAME+slot*FRAME_BYTES);
    volatile u32 *raw=(volatile u32 *)INPUT,*enh=(volatile u32 *)OUTPUT;
    memset(frame,0,FRAME_BYTES);labels(frame);
    tw=380U;th=(h*tw)/w;
    if(th>400U){th=400U;tw=(w*th)/h;}
    if(!tw)tw=1;
    if(!th)th=1;
    y0=56U+(400U-th)/2U;
    for(side=0;side<2;side++){
        x0=side*400U+(400U-tw)/2U;
        for(y=0;y<th;y++)for(x=0;x<tw;x++){
            u32 p=(y*h/th)*w+x*w/tw;
            pixel(frame,x0+x,y0+y,side?enh[p]:raw[p]);
        }
    }
    barrier();
    if(XAxiVdma_StartParking(&vdma,(int)slot,XAXIVDMA_READ)!=XST_SUCCESS)return 1;
    for(x=0;x<2000U;x++){
        if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_READ)==slot){mail[M_CURRENT]=slot;return 0;}
        usleep(1000);
    }
    return 2;
}
int main(void){
    u32 x,y,seq,h,w,control,active=0;XTime t0,t1;int status;
    /* JTAG and PL access these DDR buffers directly. Disable D-cache explicitly. */
    Xil_DCacheDisable();memset((void *)MAIL,0,4096U);
    memset((void *)FRAME,0,FRAME_BYTES*3U);
    for(y=0;y<480U;y++)for(x=0;x<800U;x++){
        u32 v=x*255U/799U;u32 rgb=v|(v<<8)|(v<<16);
        if(y<80U)rgb=x<266U?0xffU:(x<533U?0xff00U:0xff0000U);
        pixel((u8 *)FRAME,x,y,rgb);
    }
    if(XGpio_Initialize(&gpio,XPAR_AXI_GPIO_0_DEVICE_ID)!=XST_SUCCESS){fail(1,0);return 1;}
    XGpio_SetDataDirection(&gpio,1,0x07U);
    xil_printf("MULTINEX_STATIC LCD_ID=%lx\r\n",(unsigned long)lcd_id_read(&gpio,1));
    XGpio_SetDataDirection(&gpio,1,0U);
    status=run_vdma_frame_buffer(&vdma,XPAR_AXIVDMA_0_DEVICE_ID,800,480,FRAME,0,0,ONLY_READ);
    if(status!=XST_SUCCESS){fail(2,0);return 1;}
    if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_READ)!=XST_SUCCESS){fail(3,0);return 1;}
    clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);
    if(DisplayInitialize(&display,XPAR_VTC_0_DEVICE_ID)!=XST_SUCCESS){fail(4,0);return 1;}
    DisplaySetMode(&display,&VMODE_800x480);
    if(DisplayStart(&display)!=XST_SUCCESS){fail(5,0);return 1;}
    if(Xil_In32(0x43000030U)&1U){fail(6,0);return 1;} /* S2MM control RUN must stay zero. */
    pointer_reg(XMULTINEX_HLS_CONTROL_ADDR_INPUT_R_DATA,INPUT);
    pointer_reg(XMULTINEX_HLS_CONTROL_ADDR_OUTPUT_R_DATA,OUTPUT);
    pointer_reg(XMULTINEX_HLS_CONTROL_ADDR_SCRATCH_DATA,SCRATCH);
    pointer_reg(XMULTINEX_HLS_CONTROL_ADDR_DIAGNOSTICS_DATA,DIAG);
    mail[M_VERSION]=3U;mail[M_PROTOCOL]=1U;mail[M_TIMER_HZ]=COUNTS_PER_SECOND;
    mail[M_INPUT]=INPUT;mail[M_OUTPUT]=OUTPUT;mail[M_SCRATCH]=SCRATCH;mail[M_DIAG]=DIAG;
    mail[M_DISPLAY0]=FRAME;mail[M_DISPLAY1]=FRAME+FRAME_BYTES;mail[M_MAX_PIXELS]=MAX_PIXELS;
    mail[M_RGB_BYTES]=MAX_PIXELS*4U;mail[M_SCRATCH_BYTES]=MAX_PIXELS*16U;
    mail[M_CURRENT]=0;mail[M_STATE]=1;barrier();mail[M_MAGIC]=MAGIC;barrier();
    xil_printf("MULTINEX_STATIC_READY mailbox=%lx no_camera no_sd\r\n",(unsigned long)MAIL);
    while(1){
        mail[M_HEARTBEAT]++;seq=mail[M_REQUEST];
        if(seq && seq!=mail[M_DONE]){
            h=mail[M_HEIGHT];w=mail[M_WIDTH];mail[M_STATE]=2;mail[M_ERROR]=0;
            if(h<1U || h>480U || w<1U || w>800U){fail(7,seq);continue;}
            if(!(rd(0)&4U)){fail(8,seq);while(1){mail[M_HEARTBEAT]++;usleep(1000);}}
            mail[M_INPUT_HASH]=hash_bytes(INPUT,h*w*4U);
            memset((void *)OUTPUT,0xA5,h*w*4U);memset((void *)DIAG,0xA5,96U);
            wr(XMULTINEX_HLS_CONTROL_ADDR_H_DATA,h);wr(XMULTINEX_HLS_CONTROL_ADDR_W_DATA,w);
            (void)rd(XMULTINEX_HLS_CONTROL_ADDR_STATUS_CTRL);
            barrier();XTime_GetTime(&t0);wr(0,1U);active=1;
            while(active){
                control=rd(0);if(control&2U){active=0;break;}
                XTime_GetTime(&t1);mail[M_HEARTBEAT]++;
                if(t1-t0>(u64)COUNTS_PER_SECOND*120U){
                    fail(9,seq);while(1){mail[M_HEARTBEAT]++;usleep(1000);}
                }
                usleep(100);
            }
            XTime_GetTime(&t1);barrier();
            mail[M_TICKS_LO]=(u32)(t1-t0);mail[M_TICKS_HI]=(u32)((t1-t0)>>32);
            mail[M_CORE_STATUS]=rd(XMULTINEX_HLS_CONTROL_ADDR_STATUS_DATA);
            if(mail[M_CORE_STATUS]!=0U){fail(10,seq);continue;}
            mail[M_OUTPUT_HASH]=hash_bytes(OUTPUT,h*w*4U);
            if(render(h,w)){fail(11,seq);continue;}
            mail[M_DMA_ERROR]=Xil_In32(0x43000004U)&0xff0U;
            if(mail[M_DMA_ERROR]){fail(12,seq);continue;}
            mail[M_STATE]=3;barrier();mail[M_DONE]=seq;barrier();
            xil_printf("MULTINEX_STATIC_DONE seq=%lu h=%lu w=%lu ticks=%lu:%lu\r\n",(unsigned long)seq,
                (unsigned long)h,(unsigned long)w,(unsigned long)mail[M_TICKS_HI],(unsigned long)mail[M_TICKS_LO]);
        }
        usleep(1000);
    }
}
