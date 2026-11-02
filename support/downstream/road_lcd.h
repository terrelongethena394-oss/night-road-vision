#ifndef ROAD_LCD_H
#define ROAD_LCD_H
#include <stdint.h>
#define ROAD_LCD_FRAME_BASE 0x02000000U
int road_lcd_init(uint32_t *lcd_id);
int road_lcd_present(const uint32_t *raw,const float *boxes,int count,unsigned ms,unsigned photo,uint32_t *slot,uint32_t *hash,uint32_t *dma);
#endif
