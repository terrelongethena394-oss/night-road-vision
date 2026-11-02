"""Check normal workbench entry selects ABI32 and leave the road demo visible."""
from pathlib import Path
from natural_guard_lab import ROOT,CASES,PROFILES,table,apply
from photo_station_core import process_photo,STAGING
from camera_snapshot_tools import rgb,words
from car_roi_delivery_common import read,write

def main():
    assert read(ROOT/'released.json')['status']=='NATURAL32_RELEASED_AFTER_ACTUAL_BOARD_CHECKS'
    case=next(r for r in read(CASES/'complete.json')['cases'] if r['case']==3)
    result=process_photo(case['source_result']['input']['original_path'],notify=lambda s:print(s,flush=True))
    assert result['firmware_abi']==32 and result['enhancement_profile']=='natural_exposure_guard55'
    p=Path(result['packet_evidence']);old=Path(case['source_result']['packet_evidence'])
    assert (p/'boxes.f32').read_bytes()==(old/'boxes.f32').read_bytes()
    expected=words(apply(rgb(old/'raw.u32'),rgb(old/'enhanced.u32'),table(PROFILES['natural55']))).tobytes()
    assert expected==(p/'enhanced.u32').read_bytes()
    write(STAGING/'gui_last_result.json',result);write(ROOT/'default_entry_verified.json',result)
    print('NATURAL32_DEFAULT_PHOTO_ENTRY_PASS',result['output'],flush=True)

if __name__=='__main__':main()
