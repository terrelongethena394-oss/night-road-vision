/* Reuse board-proven VDMA parking and OV5640 driver; camera buffers never
 * overlap display, inference, or snapshot-result buffers. No SD/Flash calls. */
#include "road_camera.h"
#include "road_camera_io.h"
#include "xparameters.h"
#include "xgpio.h"
#include "xaxivdma.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "sleep.h"
#include "display_ctrl/display_ctrl.h"
#include "vdma_api/vdma_api.h"
#include "clk_wiz/clk_wiz.h"
#include "emio_sccb_cfg/emio_sccb_cfg.h"
#include "ov5640/ov5640_init.h"
#include <string.h>
static XAxiVdma vdma;static XGpio gpio;static DisplayCtrl display;
extern u8 sccb_read_reg16(u16);
uint32_t rc_dma_error(int write){return XAxiVdma_ReadReg(vdma.BaseAddr,write?0x34U:0x04U)&0xff0U;}
int rc_present(uint32_t selected){
 unsigned i;Xil_DCacheFlushRange(RC_FRAME+selected*RC_FRAME_BYTES,RC_FRAME_BYTES);__asm__ volatile("dsb sy" ::: "memory");
 if(XAxiVdma_StartParking(&vdma,(int)selected,XAXIVDMA_READ)!=XST_SUCCESS)return 1;
 for(i=0;i<2000;i++){if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_READ)==selected)return rc_dma_error(0)?2:0;usleep(1000);}
 return 3;
}
int rc_snapshot(uint32_t *dest,uint32_t *slot){
 uint32_t old=XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE),next,i;const uint8_t *src;
 if(old>1)return 1;
 next=1U-old;
 if(XAxiVdma_StartParking(&vdma,(int)next,XAXIVDMA_WRITE)!=XST_SUCCESS)return 2;
 for(i=0;i<2000;i++){if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_WRITE)==next)break;usleep(1000);}
 if(i==2000)return 3;
 usleep(1000);__asm__ volatile("dsb sy" ::: "memory");
 src=(const uint8_t *)(RC_CAPTURE+old*RC_FRAME_BYTES);Xil_DCacheInvalidateRange((INTPTR)src,RC_FRAME_BYTES);
 road_camera_average(src,dest);
 __asm__ volatile("dsb sy" ::: "memory");*slot=old;return rc_dma_error(1)?4:0;
}
int rc_io_init(uint32_t *lcd,uint32_t *cam){
 unsigned i;XAxiVdma_DmaSetup cfg;UINTPTR addresses[3];
 if(XGpio_Initialize(&gpio,XPAR_AXI_GPIO_0_DEVICE_ID)!=XST_SUCCESS)return 1;
 XGpio_SetDataDirection(&gpio,1,7);*lcd=lcd_id_read(&gpio,1);XGpio_SetDataDirection(&gpio,1,0);if(*lcd!=0x7084)return 2;
 memset((void *)RC_FRAME,0,RC_FRAME_BYTES*3U);Xil_DCacheFlushRange(RC_FRAME,RC_FRAME_BYTES*3U);
 if(run_vdma_frame_buffer(&vdma,XPAR_AXIVDMA_0_DEVICE_ID,800,480,RC_FRAME,0,0,ONLY_READ)!=XST_SUCCESS)return 3;
 if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_READ)!=XST_SUCCESS)return 4;
 clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);if(!(Xil_In32(XPAR_CLK_WIZ_0_BASEADDR+CLK_SR_OFFSET)&1))return 5;
 if(DisplayInitialize(&display,XPAR_VTC_0_DEVICE_ID)!=XST_SUCCESS||DisplaySetMode(&display,&VMODE_800x480)!=XST_SUCCESS||DisplayStart(&display)!=XST_SUCCESS)return 6;
 emio_init();*cam=((uint32_t)sccb_read_reg16(0x300a)<<8)|sccb_read_reg16(0x300b);
 if(*cam!=0x5640||ov5640_init(800,480,1800,1000)!=0)return 7;
 memset(&cfg,0,sizeof(cfg));cfg.VertSizeInput=480;cfg.HoriSizeInput=2400;cfg.Stride=2400;cfg.EnableCircularBuf=0;cfg.EnableSync=0;cfg.FixedFrameStoreAddr=0;
 for(i=0;i<3;i++)addresses[i]=RC_CAPTURE+i*RC_FRAME_BYTES;
 if(XAxiVdma_DmaConfig(&vdma,XAXIVDMA_WRITE,&cfg)!=XST_SUCCESS)return 8;
 if(XAxiVdma_DmaSetBufferAddr(&vdma,XAXIVDMA_WRITE,addresses)!=XST_SUCCESS)return 9;
 if(XAxiVdma_DmaStart(&vdma,XAXIVDMA_WRITE)!=XST_SUCCESS||XAxiVdma_StartParking(&vdma,0,XAXIVDMA_WRITE)!=XST_SUCCESS)return 10;
 usleep(250000);return 0;
}
