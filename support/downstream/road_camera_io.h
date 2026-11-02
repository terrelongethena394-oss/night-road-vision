#ifndef ROAD_CAMERA_IO_H
#define ROAD_CAMERA_IO_H
#include <stdint.h>
int rc_io_init(uint32_t *,uint32_t *);
int rc_snapshot(uint32_t *,uint32_t *);
int rc_present(uint32_t);
uint32_t rc_dma_error(int);
#endif
