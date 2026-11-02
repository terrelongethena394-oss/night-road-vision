"""Same-gain filter ablation; diagnosis only, never programs the board."""
from pathlib import Path
import json,hashlib
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont
import road_retinex_project as model

BASE=Path('E:/FPGA_Enhance_Work')
ROOT=BASE/'road_retinex_texture_diagnostic_20261029'
SOURCE=BASE/'road_project_retinex_20261029_r3/showcase/c81ff2c0-420a8956/raw.png'
def main():
    assert not ROOT.exists();ROOT.mkdir()
    balanced=BASE/'road_retinex_balanced_20261029_r1'
    (balanced/'manual_display_status.json').write_text(json.dumps(dict(accepted=False,status='QUALITY_REJECTED_NEEDS_TEXTURE_AND_NOISE_REVISION',user_feedback='感觉还是有问题；只有有车的位置清晰，其余区域模糊',sd_written=False),ensure_ascii=False,indent=2),encoding='utf-8')
    # Instrument a saved COPY only; leave frozen model and firmware unchanged.
    source=Path(model.__file__).read_text(encoding='utf-8')
    needle='return z,dict(mean_in=float(y.mean()),mean_out=float(oy.mean()),'
    assert source.count(needle)==1
    debug_source=source.replace(needle,'return z,dict(debug_base=base.copy(),debug_gain=gain.copy(),debug_shadow=shadow.copy(),debug_grad=grad.copy(),mean_in=float(y.mean()),mean_out=float(oy.mean()),')
    (ROOT/'instrumented_reference.py').write_text(debug_source,encoding='utf-8')
    namespace={};exec(compile(debug_source,'instrumented_reference.py','exec'),namespace)
    raw=np.array(Image.open(SOURCE).convert('RGB'));strong,debug=namespace['enhance'](raw,'project_strong')
    ordinary=model.enhance(raw,'project_strong')[0];assert np.array_equal(strong,ordinary)
    base=debug.pop('debug_base');gain=debug.pop('debug_gain');shadow=debug.pop('debug_shadow');grad=debug.pop('debug_grad')
    current=((raw.astype(np.uint16)+strong.astype(np.uint16)+1)//2).astype(np.uint8)
    unsmoothed=np.floor(np.clip(raw.astype(np.float32)*gain[:,:,None],0,255)+.5).astype(np.uint8)
    same_gain=((raw.astype(np.uint16)+unsmoothed.astype(np.uint16)+1)//2).astype(np.uint8)
    for n,a in [('raw',raw),('current50',current),('same_gain_no_rgb_smoothing',same_gain)]:Image.fromarray(a).save(ROOT/(n+'.png'))
    regions={'sky':(0,0,400,75),'vehicles_band':(0,90,400,165),'carhood':(0,180,400,240)}
    stats={}
    for name,(x1,y1,x2,y2) in regions.items():
        sl=np.s_[y1:y2,x1:x2];stats[name]=dict(mean_dark_smoothing_weight=float(shadow[sl].mean()),mean_chroma_smoothing_weight=float((shadow*(1-model.smoothstep(30,100,grad)))[sl].mean()),mean_gain=float(gain[sl].mean()))
    f=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
    canvas=Image.new('RGB',(1240,410),'white');d=ImageDraw.Draw(canvas)
    d.text((10,8),'同一张图、同一增益图：检查平滑是否抹掉纹理',font=f(22),fill='black')
    for i,(label,a) in enumerate([('原始输入',raw),('当前50%：含颜色与像素平滑',current),('诊断：去掉像素平滑、增益不变',same_gain)]):
        d.text((10+i*410,48),label,font=f(17),fill='black');canvas.paste(Image.fromarray(a),(10+i*410,84))
    d.text((10,336),'第三列是诊断消融，不是已通过的新方案；去掉平滑可能同时增加噪声。',font=f(19),fill='black')
    d.text((10,372),'无检测框参与增强；原图中的雨夜噪声/压缩信息与算法涂抹需分别处理。',font=f(19),fill='#555555')
    canvas.save(ROOT/'same_gain_ablation.png')
    # Magnified crops use identical nearest-neighbor scaling for comparison,
    # never imply recovery of resolution or newly generated scene details.
    for name,(x1,y1,x2,y2) in regions.items():
        cx1,cx2=100,300;box=(cx1,y1,cx2,y2)
        h=(y2-y1)*2;out=Image.new('RGB',(1220,h+50),'white');draw=ImageDraw.Draw(out)
        for i,(label,a) in enumerate([('RAW',raw),('CURRENT50',current),('NO SMOOTH / SAME GAIN',same_gain)]):
            draw.text((i*410+5,5),label,font=f(17),fill='black');out.paste(Image.fromarray(a).crop(box).resize((400,h),Image.Resampling.NEAREST),(i*410,40))
        out.save(ROOT/(name+'_crop2x.png'))
    result=dict(status='TEXTURE_DIAGNOSIS_ONLY_NO_BOARD_CHANGE',reference_source_sha256=hashlib.sha256(source.encode()).hexdigest(),regions=stats,debug_stats=debug,warning='Smoothed versus unsmoothed comparison fixes the gain map; the third image may increase noise. This is not an accuracy/quality win.',hardware_access=False,sd_written=False)
    (ROOT/'diagnosis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
