"""Independent full-shape and QAT-crop projects share the same revised hardware source."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
OLD=Path('E:/FPGA_Enhance_Work/road_qconv_hls_20261027')
QAT=Path('E:/FPGA_Enhance_Work/road_qconv_qatcases_20261027')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    for kind,base in [('full',OLD),('schedule',QAT)]:
        root=Path('E:/FPGA_Enhance_Work/road_qconv_r2_'+kind+'_20261027');root.mkdir(exist_ok=False)
        for n in ['road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']:shutil.copy2(HERE/n,root/n)
        shutil.copytree(base/'fixtures',root/'fixtures')
        for n in ['cases_all.txt','cases_rtl.txt','fixtures.json']:shutil.copy2(base/n,root/n)
        for n in ['csim.tcl','synth.tcl','cosim.tcl']:(root/n).write_text((OLD/n).read_text().replace(OLD.as_posix(),root.as_posix()),encoding='ascii')
        protocol=json.loads((base/'protocol.json').read_text());protocol.update(source_sha256={n:sha(root/n) for n in ['road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']},revision='R2: accumulate metadata validation before return topermit pipeline; bounded8bit search indices/bases; RGB dualwrite requestsII2 explicitly. Same valid-output arithmetic. R1 full66 passedCsim but estimated timing12.762ns/LUT44435 failed gates.',parent=str(base))
        (root/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    print('ROAD_QCONV_R2_INDEPENDENT_PROJECTS_READY',flush=True)
if __name__=='__main__':main()
