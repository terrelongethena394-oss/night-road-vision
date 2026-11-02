"""Actual user-authorized board roundtrip through the new photo workflow."""
from photo_station_core import DELIVERY,STAGING,process_photo
from car_roi_delivery_common import write
def main():
    result=process_photo(DELIVERY/'示例照片/夜间道路示例.png',force_reload=True,notify=lambda x:print(x,flush=True))
    write(STAGING/'actual_roundtrip_verified.json',result)
    write(DELIVERY/'实际上板传输验收.json',result)
    print('PHOTO_STATION_END_TO_END_ACTUAL_BOARD_PASS',result['output'],flush=True)
if __name__=='__main__':main()
