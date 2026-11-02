from photo_station_core import DELIVERY,STAGING
from car_roi_delivery_common import read,write
def main():
    r=read(STAGING/'actual_roundtrip_verified.json')
    write(DELIVERY/'实物屏幕确认.json',dict(status='USER_PHYSICAL_LCD_SYNCHRONIZATION_CONFIRMED',
        response='屏幕同步显示正常，右侧更亮',
        question='电脑端已收到增强图和汽车框。开发板屏幕现在是否也显示同一张固定夜间道路图，左侧原图、右侧更亮，且两侧有汽车框？',
        packet_evidence=r['packet_evidence'],source_sha256=r['source_sha256'],output=r['output'],
        scope='User observation of physical panel; separate from numerical readback verification.',sd_written=False))
    print('PHOTO_STATION_PHYSICAL_PANEL_CONFIRMATION_RECORDED',flush=True)
if __name__=='__main__':main()
