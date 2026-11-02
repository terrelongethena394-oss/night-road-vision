"""Reuse frozen physical timer receipts; do not perturb the running board."""
from pathlib import Path
import hashlib,json,statistics,struct
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
BASE=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1/physical_full_r1')
def main():
    records={}
    for label in ['cpu','hybrid']:
        rows=[]
        for j in [1,2,3]:
            p=BASE/f'{label}_timing{j}.bin';raw=p.read_bytes();m=struct.unpack('<80I',raw);assert m[1]==11 and m[6]==m[35]==m[41]==m[62]==m[74]==0
            def seconds(i):return (m[i]+(m[i+1]<<32))/m[18]
            rows.append(dict(total=seconds(19),network=seconds(21),preprocess=seconds(23),postprocess=seconds(25),pl_call_span_including_callback_service=seconds(75),preview_updates=m[70],source_sha256=hashlib.sha256(raw).hexdigest()))
        records[label]=dict(runs=rows,medians={key:statistics.median(r[key] for r in rows) for key in ['total','network','preprocess','postprocess','pl_call_span_including_callback_service']})
    h=records['hybrid']['medians'];result=dict(status='PHYSICAL_EXISTING_RECEIPT_BREAKDOWN_NOT_NEW_BOARD_PROFILE',records=records,network_fraction=h['network']/h['total'],remaining_network_span=h['network']-h['pl_call_span_including_callback_service'],notes='PL call spans include ARM polling/cache/service; subtraction is not a hardware compute-only profile. Preview callback cost depends on total duration. Do not turn host/HLS estimates into FPS.',architecture_candidate=dict(arithmetic='W8/A8 exact integer sums and threshold SiLU',pe=16,simd=8,proposed_macs_per_clock=128,target_clock_mhz=100,scope='all60 conv including1x1,3x3,first6x6; residual/pool/upcat/decode onARM initially',target='Investigate 5FPS stage goal, no guaranteed rate'),hardware_access=False,sd_written=False)
    (ROOT/'baseline_breakdown.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
