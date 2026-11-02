"""Process a static photograph with project Retinex + existing vehicle detector.

Default: raw image detection overlaid on enhanced display, explicitly recorded.
No board/SD access. Requires existing local fixed C detector and weights.
"""
from pathlib import Path
import argparse,json,subprocess,os,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from road_retinex_project import enhance,PRESETS
from road_enhance_common import enhance as gamma
from study_road_local_enhance import resize400,panel

BASE=Path('E:/FPGA_Enhance_Work')
APP=BASE/'road_conv13_p16_runtime_20261028_r1/firmware'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--preset',choices=PRESETS,default='project_strong');args=p.parse_args()
    assert args.input.is_file();assert not args.output.exists(),'Choose a new output directory to preserve results'
    args.output.mkdir(parents=True)
    original=np.array(Image.open(args.input).convert('RGB'));raw=resize400(original);z,stats=enhance(raw,args.preset);old=gamma(raw,1,32)[0]
    for name,a in [('raw',raw),('old_gamma',old),('enhanced',z)]:Image.fromarray(a).save(args.output/(name+'.png'))
    # Narrow-character C runtimes use an ASCII scratch directory; the user
    # output can contain Chinese characters and is handled via Python/Pillow.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='photo_',dir=BASE/'road_project_retinex_20261029_r3') as temp:
        folder=Path(temp);assert folder.resolve().is_relative_to((BASE/'road_project_retinex_20261029_r3').resolve())
        b=raw.astype(np.uint32);(b[:,:,0]|b[:,:,1]<<8|b[:,:,2]<<16).astype('<u4').tofile(folder/'input.u32')
        exe=BASE/'road_local_enhance_20261029_r2/host/road_ap.exe';proof=json.loads((exe.parent/'build.json').read_text(encoding='utf-8'))
        assert sha(exe)==proof['exe_sha256'] and sha(APP/'runtime/weights.f32')==proof['weights_sha256']
        env=dict(os.environ);env['PATH']='E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin;'+env['PATH']
        run=subprocess.run([str(exe),str(APP/'runtime/weights.f32'),str(folder/'input.u32'),str(folder)],capture_output=True,text=True,env=env,timeout=90)
        assert run.returncode==0 and 'ROAD_FP32_HOST_DONE' in run.stdout,(run.stdout,run.stderr)
        boxes=np.fromfile(folder/'boxes400.f32','<f4').reshape(-1,6);boxes=boxes[(boxes[:,4]>=.25)&(boxes[:,5]>=1)]
        boxes.astype('<f4').tofile(args.output/'vehicle_boxes400.f32')
    view=Image.fromarray(z);draw=ImageDraw.Draw(view);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',11)
    for x1,y1,x2,y2,score,cls in boxes:
        draw.rectangle((x1,y1,x2,y2),outline='cyan',width=1)
        draw.text((max(0,x1),max(0,y1-12)),f'{["PERSON","CAR","TRUCK","BUS"][int(cls)]} {score:.2f}',font=font,fill='cyan')
    view.save(args.output/'enhanced_vehicle_detection.png')
    panel([raw,old,z,np.array(view)],['原图RGB888','旧保守Gamma','项目定制增强','增强显示＋原图检测'],args.input.name,args.output/'comparison.png',note='电脑实际处理；检测输入为原图，不能据此声称增强提升检测；无SD或板卡操作。')
    result=dict(input=str(args.input.resolve()),source_sha256=sha(args.input),input_format='RGB888400x240 from same800x480 average profile',enhancer='Project-written classical Retinex, not a neural network',parameters=PRESETS[args.preset],stats=stats,detector_input='raw RGB888',weights_sha256=sha(APP/'runtime/weights.f32'),vehicle_predictions=boxes.tolist(),warning='Prediction count is not accuracy; no truth labels supplied for this input.',hardware_access=False,sd_written=False)
    (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PROJECT_PHOTO_COMPLETE',args.output,flush=True)
if __name__=='__main__':main()
