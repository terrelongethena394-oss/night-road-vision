#ifndef ROAD_CAMERA_H
#define ROAD_CAMERA_H
#include <stdint.h>
#define RC_FRAME_BYTES (800U*480U*3U)
#define RC_FRAME 0x02000000U
#define RC_CAPTURE 0x06000000U
#define RC_INPUT 0x10000000U
#define RC_WEIGHT 0x11000000U
#define RC_ARENA 0x12000000U
#define RC_DECODE 0x13000000U
#define RC_PREP 0x13200000U
#define RC_CANDIDATES 0x13400000U
#define RC_KEEP 0x13500000U
#define RC_BOX400 0x13600000U
#define RC_BOX320 0x13610000U
#define RC_MAIL 0x13800000U
#define RC_TRACE 0x14000000U
/* Keep camera/result copies above the original20MiB debug trace region. */
#define RC_LIVE 0x16000000U
#define RC_RESULT 0x16100000U
#define RC_RESULT_BOX 0x16200000U
#define RC_RESULT_DECODE 0x16300000U
#define RC_RESULT_HEAD 0x16400000U
#define RC_UI 0x16500000U
#define RC_ENH_INPUT 0x16600000U
#define RC_RAW_RESULT 0x16700000U
#define RC_ROI_LIVE 0x16800000U
#define RC_ROI_INPUT 0x16900000U
#define RC_ROI_RESULT 0x16A00000U
#define RC_FULL_BOX 0x17000000U
#define RC_ROI_BOX 0x17010000U
#define RC_FUSED_BOX 0x17020000U
#define RC_FULL_DECODE 0x17100000U
#define RC_FULL_HEAD 0x17200000U
#define RC_FULL_PREP 0x17300000U
#define RC_RAW_BYTES (400U*240U*4U)
typedef struct {
 uint32_t live_id,result_id,active_id,detect_ms,age_ms,view_hz10;
 uint32_t count,has_result,is_test,paused,busy;
 uint32_t mean_luma,enh_alpha,enh_cap,pipe_mode,detail_mode;
 uint32_t baseline_count;
} RoadCameraUI;
int road_camera_draw(uint8_t *,const uint32_t *,const uint32_t *,const float *,const float *,const RoadCameraUI *);
void road_camera_average(const uint8_t *,uint32_t *);
/* Safe cooperative service only: must not alter weights, arena or inference input. */
void road_set_service(void (*fn)(void *),void *opaque);
#endif
