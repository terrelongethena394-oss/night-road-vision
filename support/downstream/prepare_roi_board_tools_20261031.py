from pathlib import Path
import os,subprocess,shutil
from car_roi_delivery_common import *
def main():
    board=ROOT/'board_candidate';app=board/'firmware';src=app/'source';out=app/'host';assert (board/'engineering_experiment_policy.json').exists()
    (out/'post_stub.c').write_text('#include "road_pl.h"\nint road_pl_try(int n,const RoadOp *o,const RoadTensor *i,const RoadTensor *t,const float *a,const float *w,float *b,void (*p)(void)){(void)n;(void)o;(void)i;(void)t;(void)a;(void)w;(void)b;(void)p;return 0;}\n',encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=dict(os.environ);env['PATH']=str(gcc.parent)+';'+env['PATH'];cmd=[str(gcc),'-shared','-O2','-std=c99','-fno-fast-math','-ffp-contract=off','-msse2','-mfpmath=sse','-I'+str(src),str(src/'road_fp32.c'),str(out/'post_stub.c'),'-lm','-o',str(out/'post.dll')];p=subprocess.run(cmd,capture_output=True,text=True,env=env);(out/'post_build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    write(out/'post_build.json',dict(command=cmd,dll_sha256=sha(out/'post.dll'),nms_source_sha256=sha(src/'road_fp32.c')))
    write(board/'physical_acceptance_policy.json',dict(status='FROZEN_BEFORE_ABI30_HARDWARE_PACKETS',engineering_only=True,joint_model_superiority_study_accepted=False,
      program='Exact pretestcompiled ABI30/weights/oldPLbit;noSDorFlash.',cases=['night_road0','night_road1','gray96','black','camera','night_road0_repeat'],
      checks='ActualJTAGsource,mailABI/sensor/LCD/FNV/PLcallcounts. RAWaverage/native400/zoom/ROIinputpixels byteexact toCPU. Derive commonRAW7 postfromACTUALdecodedNN outputs plusARMrefinerpayload,comparefullcommon andROIplan. Refineroutputs vsCPU max.001mean.00002. FinalROIpost vsC fromactualNN outputs coords.005score.00002/classesexact. Retinexdisplay vshostmax1mean.01. Exactframebufferrasterization.',
      network_numeric='Sameoperationalpolicyregisteredbeforeindependenttest:allactualboardNNinputstoCPUreference;decodeprobmax.00002,mean.00002;postNMSscore>=.01 count/classesexact,coords.005/score.00002;rawdecodedmax.001 remainsdiagnostic,neverpretendpassediffailed.',
      repeat='Sameinjectedsource yieldssameinput/hash/ROIplans/predictions;camera issinglecapture,notrealtimeclaim.',
      restore='Onengineeringfailure attemptrestorepriorABI29;reportiflinkpreventsrestoration.',
      candidate_elf_sha256=sha(app/'road_detail.elf'),roi_weights_sha256=sha(app/'runtime/roi_weights.f32'),post_dll_sha256=sha(out/'post.dll'),render_exe_sha256=sha(out/'render.exe'),independent_result_sha256=sha(ROOT/'confirmation/fresh_result.json'),sd_written=False))
    shutil.copy2(__file__,board/Path(__file__).name);print('ROI_BOARD_HOST_VALIDATOR_DEPENDENCIES_READY',flush=True)
if __name__=='__main__':main()
