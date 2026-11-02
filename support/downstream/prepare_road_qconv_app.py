"""Host-prove all60-conv experimental firmware wiring, preserve deployed FP32 app."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
ROOT=Path('E:/FPGA_Enhance_Work/road_qconv_app_20261027')
QAT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ROOT.mkdir(exist_ok=False);src=ROOT/'source';shutil.copytree(CAM/'source',src)
    selected=json.loads((QAT/'selection_complete.json').read_text());quant=QAT/'exports'/f'epoch{selected["selected_epoch"]}'
    for n in ['road_graph.h','road_q8_tables.h']:shutil.copy2(quant/n,src/n)
    for n in ['road_qconv_arm.c','road_qconv_arm.h','road_qconv_pack.c']:shutil.copy2(HERE/n,src/n)
    shutil.copy2(QAT/'hardware_model/road_qconv_layout.h',src/'road_qconv_layout.h')
    old=(CAM/'source/road_fp32.c').read_text();base=(NN/'source_r2/road_fp32.c').read_text()
    service=old[old.index('static void (*road_service_callback)'):old.index('#include <math.h>')]
    prefix=base[base.index('static float sigmoid'):base.index('void road_input320')];suffix=base[base.index('void road_decode'):]
    code=(HERE/'road_q8_kernel.inc').read_text()
    needle='for(y=0;y<out->h;y++)for(x=0;x<out->w;){';assert code.count(needle)==1
    code=code.replace(needle,'for(y=0;y<out->h;y++){for(x=0;x<out->w;){')
    tail='x+=tile;\n  }\n}\nint road_forward';assert code.count(tail)==1
    code=code.replace(tail,'x+=tile;\n  }road_poll_service();}\n}\nint road_forward')
    needle='if(op->kind==1)qconv(i,op,in,out,a,model,b);';assert code.count(needle)==1
    code=code.replace(needle,'if(op->kind==1){int used=qhw_try(i,op,in,out,a,model,b,road_poll_service);if(used<0)return used;if(!used)qconv(i,op,in,out,a,model,b);}')
    code=code.replace('if(trace)trace(i,(const float *)b','road_poll_service();\n    if(trace)trace(i,(const float *)b')
    header='#include "road_fp32.h"\n#include "road_qconv_arm.h"\n#include <math.h>\n#include <stdlib.h>\n#include <string.h>\n'
    (src/'road_fp32.c').write_text(header+service+prefix+code+suffix,encoding='ascii')
    harness=(HERE/'road_fp32_host.c').read_text().replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_qconv_arm.h"')
    harness=harness.replace('road_preprocess400(raw,rgb);','if(qhw_prepare((const unsigned char *)weights))return 20;\n  qhw_begin();\n  road_preprocess400(raw,rgb);')
    hw=json.loads((QAT/'hardware_model/complete.json').read_text());meta=(QAT/'hardware_model/metadata.bin').stat().st_size;packed=(QAT/'hardware_model/packed_weights.bin').stat().st_size
    harness=harness.replace('free(weights);free(arena);',f'printf("EXACT_PACKED_HW_EMULATION_CALLS=%u\\n",qhw_host_calls);if(qhw_host_calls!=60)return 21;\n  snprintf(path,sizeof(path),"%s/packed.bin",argv[3]);if(writefile(path,qhw_host_weights(),{packed}U))return 22;\n  snprintf(path,sizeof(path),"%s/metadata.bin",argv[3]);if(writefile(path,qhw_host_metadata(),{meta}U))return 23;\n  free(weights);free(arena);')
    (src/'qconv_host.c').write_text(harness,encoding='ascii');host=ROOT/'host';host.mkdir()
    env=os.environ.copy();env['PATH']=str(GCC.parent)+';'+env['PATH'];cmd=[str(GCC),'-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-DQCONV_EMULATE','-I'+str(src),*[str(src/n) for n in ['road_fp32.c','road_qconv_arm.c','road_qconv_pack.c','qconv_host.c']],'-lm','-o',str(host/'qconv_host.exe')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(host/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    results=[]
    for f in json.loads((NN/'export_complete.json').read_text())['fixtures']:
        name=f['name'];out=host/name;out.mkdir();tr=out/'trace';tr.mkdir()
        p=subprocess.run([str(host/'qconv_host.exe'),str(quant/'qmodel.bin'),str(NN/'cases'/name/'input400.u32'),str(out),str(tr)],env=env,capture_output=True,text=True,check=True)
        assert 'EXACT_PACKED_HW_EMULATION_CALLS=60' in p.stdout
        for q in (quant/'host'/name/'trace').iterdir():assert q.read_bytes()==(tr/q.name).read_bytes(),(name,q.name)
        for n in ['decoded.f32','boxes400.f32','boxes320.f32','input320.rgb']:assert (out/n).read_bytes()==(quant/'host'/name/n).read_bytes(),(name,n)
        assert sha(out/'packed.bin')==hw['packed_sha256'] and sha(out/'metadata.bin')==hw['metadata_sha256']
        results.append(dict(name=name,all86_tensors_decode_nms_bytes_exact=True,packed_weights_and_metadata_exact=True,emulated_calls=60));print('ROAD_QCONV_APP_HOST_ALL86_EXACT',name,flush=True)
    quality=json.loads((QAT/'final_holdout_complete.json').read_text())
    (ROOT/'host_complete.json').write_text(json.dumps(dict(status='EXPERIMENTAL_Q8_ALL60_PACKED_CONV_HOST_INTEGRATION_ALL8_ALL86_EXACT',results=results,quant_model_sha256=sha(quant/'qmodel.bin'),source_sha256={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()},quality_gate_passed=quality['passed'],default_promotion_allowed=False,hardware_access=False,sd_written=False),indent=2),encoding='utf-8');print('ROAD_QCONV_APP_HOST_PASS_EXPERIMENT_ONLY',flush=True)
if __name__=='__main__':main()
