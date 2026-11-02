/* GPL-3.0. Exact W8/A8 convolution plus offline SiLU thresholds. */
#ifndef ROAD_QCONV_HLS_H
#define ROAD_QCONV_HLS_H
#include <ap_int.h>
typedef ap_uint<64> QWord;
typedef ap_uint<128> OutWord;
typedef ap_uint<256> MetaWord;
#define Q_PE 16
#define Q_SIMD 8
#define Q_TILE 16
#define Q_CHUNK 64
#define Q_PATCH_WORDS 2048
#define Q_MAX_RED_GROUPS 144
#define Q_MAX_TABLE 2097152
int road_qconv(const QWord *input,const QWord *weights,const MetaWord *metadata,const ap_int<32> *tables,OutWord *output,int height,int width,int ic4,int oc4,int kernel,int stride,int unsigned_input,int head,int table_count);
#endif
