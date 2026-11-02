#ifndef ROAD_CAPTURE_VIEWS_H
#define ROAD_CAPTURE_VIEWS_H
#include <stdint.h>
/* One immutable BGR800x480 frame -> RGB words for full400 and three crops.
 * Caller provides four separate 96000-word destinations, outside the source.
 */
int road_capture_views(const uint8_t *,uint32_t *,uint32_t *,uint32_t *,uint32_t *);
#endif
