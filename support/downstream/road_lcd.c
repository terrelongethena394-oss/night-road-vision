/* LCD/VDMA integration for the known V3.9 7020 / 800x480 display platform.
 * Reuses the vendor drivers with their original notices. No camera capture. */
#include "road_lcd.h"
#include "road_lcd_draw.h"
#include "xparameters.h"
#include "xgpio.h"
#include "xaxivdma.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "sleep.h"
#include "display_ctrl/display_ctrl.h"
#include "vdma_api/vdma_api.h"
#include "clk_wiz/clk_wiz.h"
static XAxiVdma vdma;static XGpio gpio;static DisplayCtrl display;static uint32_t current;
int road_lcd_init(uint32_t *lcd_id){
 unsigned i;
 if(XGpio_Initialize(&gpio,XPAR_AXI_GPIO_0_DEVICE_ID)!=XST_SUCCESS)return 1;
 XGpio_SetDataDirection(&gpio,1,7);*lcd_id=lcd_id_read(&gpio,1);XGpio_SetDataDirection(&gpio,1,0);
 if(*lcd_id!=0x7084U)return 2;
 for(i=0;i<3;i++)road_lcd_waiting((uint8_t *)(ROAD_LCD_FRAME_BASE+i*ROAD_LCD_FRAME_BYTES));
 Xil_DCacheFlushRange(ROAD_LCD_FRAME_BASE,ROAD_LCD_FRAME_BYTES*3U);
 if(run_vdma_frame_buffer(&vdma,XPAR_AXIVDMA_0_DEVICE_ID,800,480,ROAD_LCD_FRAME_BASE,0,0,ONLY_READ)!=XST_SUCCESS)return 3;
 if(XAxiVdma_StartParking(&vdma,0,XAXIVDMA_READ)!=XST_SUCCESS)return 4;
 clk_wiz_cfg(XPAR_CLK_WIZ_0_DEVICE_ID,VMODE_800x480.freq);
 if(DisplayInitialize(&display,XPAR_VTC_0_DEVICE_ID)!=XST_SUCCESS)return 5;
 if(DisplaySetMode(&display,&VMODE_800x480)!=XST_SUCCESS)return 6;
 if(DisplayStart(&display)!=XST_SUCCESS)return 7;
 current=0;return 0;
}
int road_lcd_present(const uint32_t *raw,const float *boxes,int count,unsigned ms,unsigned photo,uint32_t *slot,uint32_t *hash,uint32_t *dma){
 uint32_t selected=1U-current,i,fnv=2166136261U,address=ROAD_LCD_FRAME_BASE+selected*ROAD_LCD_FRAME_BYTES;uint8_t *frame=(uint8_t *)address;
 int status=road_lcd_draw(frame,raw,boxes,count,ms,photo);if(status)return 10-status;
 for(i=0;i<ROAD_LCD_FRAME_BYTES;i++)fnv=(fnv^frame[i])*16777619U;
 Xil_DCacheFlushRange(address,ROAD_LCD_FRAME_BYTES);__asm__ volatile("dsb sy" ::: "memory");
 if(XAxiVdma_StartParking(&vdma,(int)selected,XAXIVDMA_READ)!=XST_SUCCESS)return 20;
 for(i=0;i<2000;i++){
  if(XAxiVdma_CurrFrameStore(&vdma,XAXIVDMA_READ)==selected){
   *dma=XAxiVdma_ReadReg(vdma.BaseAddr,XAXIVDMA_SR_OFFSET)&0x00000FF0U;
   if(*dma)return 21;
   current=selected;*slot=selected;*hash=fnv;return 0;
  }
  usleep(1000);
 }
 return 22;
}
