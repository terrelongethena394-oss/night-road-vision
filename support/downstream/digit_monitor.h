#pragma once
#include <ap_int.h>
#include <ap_axi_sdata.h>
#include <hls_stream.h>
typedef ap_axiu<24,1,1,1> video_pixel;
void digit_monitor(hls::stream<video_pixel>& input,hls::stream<video_pixel>& output,
 int height,int width,int roi_x,int roi_y,int which,int ui_digits,
 int &prediction,int &margin,int &frame_count,int &result);
