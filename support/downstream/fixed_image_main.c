/* Separate volatile image-test application. No camera initialization or S2MM start.
 * FPGA enhancement/classification bitstream and frozen weights are unchanged. */
#include <string.h>
#include "xparameters.h"
#include "xil_types.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "sleep.h"
#include "xgpio.h"
#include "xaxivdma.h"
#include "digit_regs.h"
#include "display_ctrl/display_ctrl.h"
#include "vdma_api/vdma_api.h"
#include "clk_wiz/clk_wiz.h"

#define RAW_BASE 0x43C30000U
#define ENH_BASE 0x43C40000U
#define NN_BASE 0x43C20000U
#define FRAME_BASE 0x02000000U
#define FRAME_BYTES (800U*480U*3U)
#define MAIL_BASE 0x03000000U
#define MAGIC 0x494D4754U
enum {M_MAGIC=0,M_VERSION,M_STATUS,M_REQUEST,M_SLOT,M_DONE,M_RAW,M_ENH,
      M_FRAME,M_RAW_MARGIN,M_ENH_MARGIN,M_CHECKSUM,M_DMA_ERRORS,M_ERROR,
      M_CURRENT_SLOT,M_HEARTBEAT,M_RESERVED,M_SLOT0_ADDR,M_SLOT1_ADDR,M_BYTES};
static volatile u32 * const mail=(volatile u32 *)MAIL_BASE;
static XAxiVdma vdma;
static DisplayCtrl display;
static XGpio gpio;
static void barrier(void) {__asm__ volatile("dsb sy" ::: "memory");}
static u32 read_word(u32 base,u32 offset) {return Xil_In32(base+offset);}
static int configure_digit(u32 base,u32 which) {
    Xil_Out32(base+DIGIT_REG_HEIGHT,480U);
    Xil_Out32(base+DIGIT_REG_WIDTH,800U);
    Xil_Out32(base+DIGIT_REG_ROI_X,480U);
    Xil_Out32(base+DIGIT_REG_ROI_Y,112U);
    Xil_Out32(base+DIGIT_REG_WHICH,which);
    Xil_Out32(base+DIGIT_REG_UI_DIGITS,0xAAU);
    if(read_word(base,DIGIT_REG_HEIGHT)!=480U || read_word(base,DIGIT_REG_WIDTH)!=800U
       || read_word(base,DIGIT_REG_ROI_X)!=480U || read_word(base,DIGIT_REG_ROI_Y)!=112U) return 1;
    Xil_Out32(base,0x81U);
    return 0;
}
static u32 checksum(u32 address) {
    volatile u8 *p=(volatile u8 *)address;
    u32 hash=2166136261U;
    unsigned i;
    for(i=0;i<FRAME_BYTES;i++) hash=(hash^p[i])*16777619U;
    return hash;
}
static void update_hud(void) {
    u32 r=read_word(RAW_BASE,DIGIT_REG_RESULT);
    u32 e=read_word(ENH_BASE,DIGIT_REG_RESULT);
    u32 r2=read_word(RAW_BASE,DIGIT_REG_RESULT);
    if(r==r2 && (r>>4)!=0U && (r>>4)==(e>>4))
        Xil_Out32(ENH_BASE+DIGIT_REG_UI_DIGITS,(r&15U)|((e&15U)<<4));
}
static void fail(u32 code,u32 sequence) {
    mail[M_ERROR]=code;mail[M_STATUS]=4U;
    barrier();mail[M_DONE]=sequence;barrier();
    xil_printf("IMAGE_ERROR code=%lu seq=%lu\r\n",(unsigned long)code,(unsigned long)sequence);
}
int main(void) {
    u32 i,x,y,sequence,slot,start_frame,r,e,r2,attempt;
    int status;
    u8 *pixels=(u8 *)FRAME_BASE;
    /* Host writes DDR directly through JTAG. Avoid cached mailbox/frame copies. */
    Xil_DCacheDisable();
    memset((void *)MAIL_BASE,0,4096U);
    mail[M_VERSION]=1U;mail[M_STATUS]=0U;
    mail[M_SLOT0_ADDR]=FRAME_BASE;mail[M_SLOT1_ADDR]=FRAME_BASE+FRAME_BYTES;
    mail[M_BYTES]=FRAME_BYTES;
    memset(pixels,0,FRAME_BYTES*3U);
    /* Initial grayscale ramp plus red/green/blue bars, same scene on both halves. */
    for(y=0;y<480U;y++) for(x=0;x<800U;x++) {
        u32 local=x%400U,at=(y*800U+x)*3U;
        u8 rr=(u8)(local*255U/399U),gg=rr,bb=rr;
        if(y<80U) {rr=local<133U?255U:0U;gg=local>=133U&&local<266U?255U:0U;bb=local>=266U?255U:0U;}
        pixels[at]=bb;pixels[at+1U]=gg;pixels[at+2U]=rr;
    }
    XGpio_Initialize(&gpio,XPAR_AXI_GPIO_0_DEVICE_ID);
    XGpio_SetDataDirection(&gpio,1,0x07U);
    xil_printf("IMAGE_TEST LCD_ID=0x%lx\r\n",(unsigned long)lcd_id_read(&gpio,1));
    XGpio_SetDataDirection(&gpio,1,0U);
    if(configure_digit(RAW_BASE,0U)||configure_digit(ENH_BASE,1U)) {fail(1,0);return 1;}
    Xil_Out32(NN_BASE+0x10U,480U);Xil_Out32(NN_BASE+0x18U,800U);Xil_Out32(NN_BASE+0x20U,1U);
    Xil_Out32(NN_BASE,0x81U);
    /* ReadSetup in this separate source copy disables genlock; no camera writer. */
    status=run_vdma_frame_buffer(&vdma,XPAR_AXIVDMA_0_DEVICE_ID,800,480,FRAME_BASE,0,0,ONLY_READ);
    if(status!=XST_SUCCESS) {fail(2,0);return 1;}
    if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_READ)!=XST_SUCCESS) {fail(3,0);return 1;}
    clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);
    DisplayInitialize(&display,XPAR_VTC_0_DEVICE_ID);
    DisplaySetMode(&display,&VMODE_800x480);
    DisplayStart(&display);
    if(Xil_In32(0x43000030U)&1U) {fail(4,0);return 1;}
    mail[M_CURRENT_SLOT]=0U;mail[M_STATUS]=1U;barrier();mail[M_MAGIC]=MAGIC;barrier();
    xil_printf("IMAGE_TEST_READY no_camera no_s2mm slots=0x%lx,0x%lx mailbox=0x%lx\r\n",
        (unsigned long)FRAME_BASE,(unsigned long)(FRAME_BASE+FRAME_BYTES),(unsigned long)MAIL_BASE);
    while(1) {
        mail[M_HEARTBEAT]++;
        update_hud();
        sequence=mail[M_REQUEST];
        if(sequence!=0U && sequence!=mail[M_DONE]) {
            mail[M_STATUS]=2U;mail[M_ERROR]=0U;
            slot=mail[M_SLOT];
            if(slot>1U||slot==mail[M_CURRENT_SLOT]) {fail(5,sequence);continue;}
            /* No target label or expected prediction is supplied to the board. */
            mail[M_CHECKSUM]=checksum(FRAME_BASE+slot*FRAME_BYTES);
            if(XAxiVdma_StartParking(&vdma,(int)slot,XAXIVDMA_READ)!=XST_SUCCESS) {fail(6,sequence);continue;}
            for(attempt=0;attempt<3000U;attempt++) {
                if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_READ)==slot) break;
                usleep(1000);
            }
            if(attempt==3000U) {fail(7,sequence);continue;}
            mail[M_CURRENT_SLOT]=slot;
            start_frame=read_word(RAW_BASE,DIGIT_REG_RESULT)>>4;
            /* Wait past three complete classifier frames, then latch an equal-ID pair. */
            for(attempt=0;attempt<3000U;attempt++) {
                r=read_word(RAW_BASE,DIGIT_REG_RESULT);
                e=read_word(ENH_BASE,DIGIT_REG_RESULT);
                r2=read_word(RAW_BASE,DIGIT_REG_RESULT);
                if(r==r2 && (r>>4)==(e>>4) && (r>>4)>=start_frame+3U) break;
                usleep(1000);
            }
            if(attempt==3000U) {fail(8,sequence);continue;}
            mail[M_RAW]=r&15U;mail[M_ENH]=e&15U;mail[M_FRAME]=r>>4;
            mail[M_RAW_MARGIN]=read_word(RAW_BASE,DIGIT_REG_MARGIN);
            mail[M_ENH_MARGIN]=read_word(ENH_BASE,DIGIT_REG_MARGIN);
            mail[M_DMA_ERRORS]=Xil_In32(0x43000004U)&0xff0U;
            if(mail[M_DMA_ERRORS]) {fail(9,sequence);continue;}
            Xil_Out32(ENH_BASE+DIGIT_REG_UI_DIGITS,(r&15U)|((e&15U)<<4));
            mail[M_STATUS]=3U;barrier();mail[M_DONE]=sequence;barrier();
            xil_printf("IMAGE_RESULT seq=%lu raw=%lu enh=%lu frame=%lu checksum=0x%lx\r\n",
                (unsigned long)sequence,(unsigned long)(r&15U),(unsigned long)(e&15U),
                (unsigned long)(r>>4),(unsigned long)mail[M_CHECKSUM]);
        }
        usleep(1000);
    }
    (void)i;
    return 0;
}
