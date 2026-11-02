"""Render actual board RGB buffers as labeled comparisons without pixel edits."""
from pathlib import Path
import hashlib,json,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
BOARD=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
OUT=HERE.parents[1]/'增强前后效果图_20261026'
FONT='C:/Windows/Fonts/msyh.ttc'
def f(size):return ImageFont.truetype(FONT,size)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def panel(rows,title):
    width=1216;height=136+len(rows)*184+50
    canvas=Image.new('RGB',(width,height),'#f4f6f8');d=ImageDraw.Draw(canvas)
    d.text((24,14),title,font=f(30),fill='#172436')
    d.text((24,57),'同一实板处理记录；展示同一车牌ROI；未对结果额外提亮、锐化或归一化',font=f(21),fill='#44546a')
    xs=[24,416,808]
    for x,label in zip(xs,['RAW 原图','NET 纯神经网络增强','AUTO 最终保护输出']):
        d.text((x,97),label,font=f(24),fill='#172436')
    for i,row in enumerate(rows):
        y=136+i*184
        note='回退原图' if row['fallback'] else ('正常光旁路' if row['protection']['alpha']==0 else '使用增强／混合输出')
        d.text((24,y),f'{i+1}. 标注：{row["truth"]}    最终策略：{note}',font=f(22),fill='#172436')
        for j,(x,array) in enumerate(zip(xs,row['arrays'])):
            # Paste source ROI directly: same pixel values and size, no resampling.
            canvas.paste(Image.fromarray(array),(x,y+35))
            ok=row['displayed'][j]==row['truth']
            d.text((x,y+137),'识别：'+row['displayed'][j]+('  正确' if ok else '  错误／拒识'),font=f(21),fill='#14603b' if ok else '#a12c30')
    d.text((24,height-39),'NET变亮不代表识别一定改善；--表示拒识。照片回放不等于真实夜景摄像头测试。',font=f(21),fill='#44546a')
    return canvas

def main():
    OUT.mkdir(exist_ok=False);individual=OUT/'单张对比';individual.mkdir()
    cases=json.loads((BOARD/'board_deployed.json').read_text(encoding='utf-8'))['cases']
    metadata=[];groups={1.:[],.25:[]}
    for row in cases:
        if row['truth'] is None:continue
        folder=BOARD/'board_plate'/row['id']
        verification=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
        assert verification['rgb_output_exact'] and verification['lcd_pixels_exact']
        files=[folder/n for n in ['input32.bin','output32.bin','protected32.bin']]
        arrays=[np.fromfile(p,np.uint8).reshape(240,400,4)[72:168,8:392,:3].copy() for p in files]
        row={**row,'arrays':arrays};groups[row['gain']].append(row)
        name=row['id']+'_'+row['truth']+'.png'
        panel([row],('人工暗化25%输入' if row['gain']==.25 else '原始亮度输入')+'｜实板增强对比').save(individual/name)
        metadata.append({k:v for k,v in row.items() if k!='arrays'}|dict(roi=[8,72,384,96],source_files=[str(p) for p in files],source_sha256=[sha(p) for p in files],comparison='单张对比/'+name))
    panel(groups[.25],'实板增强前后对比｜人工暗化到25%（非实拍夜景）').save(OUT/'人工暗化_六组对比.png')
    panel(groups[1.],'实板增强前后对比｜原始亮度').save(OUT/'原始亮度_六组对比.png')
    (OUT/'来源与结果.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'说明.md').write_text('''# 增强前后的实板效果

左RAW原图，中NET纯增强输出，右AUTO最终保护输出。所有图像来自已验证的7020实板DDR缓存，截取同一ROI(8,72,384,96)，拼图未改变原像素亮度、色彩或清晰度；拼图文字是事后统计说明，不是开发板界面。

人工暗化图为六张公开真实车牌裁剪统一按RGB亮度乘0.25后再送板处理，不是实拍夜景。原始亮度与人工暗化来自同一批六张照片；不是十二个独立场景。增强不等于一定识别更准确；图中保留识别错误和拒识结果。

第一张暗化苏E13TZ0，纯增强后被识别为苏EJ3TZ0，因此最终AUTO退回原图；最后一张标注京NWZ388，RAW及AUTO读为京NKZ388，仍是错误，不能把输出合法号码视作正确。

数据来自CCPD公开裁剪及其社区镜像；原记录和出处在E:/FPGA_Enhance_Work/license_plate_20261026。全部十二组来源路径、源文件哈希、真值与三路结果在来源与结果.json。当前增强模型为Multinex，识别为ARM TinyPlate。无需重新下载模型即可查看这些历史实板结果。
''',encoding='utf-8')
    archive=OUT.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print('ACTUAL_BOARD_COMPARISONS_EXPORTED',len(metadata),str(archive),flush=True)
if __name__=='__main__':main()
