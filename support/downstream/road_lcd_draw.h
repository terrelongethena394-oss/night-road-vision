#ifndef ROAD_LCD_DRAW_H
#define ROAD_LCD_DRAW_H
#include <stdint.h>
#define ROAD_LCD_FRAME_BYTES (800U*480U*3U)
int road_lcd_draw(uint8_t *bgr,const uint32_t *rgb400,const float *boxes,int count,unsigned milliseconds,unsigned photo);
void road_lcd_waiting(uint8_t *bgr);
#endif
