"""Prepare a reviewable local candidate, not a claim of hardware acceptance."""
import shutil,ast,runpy,tkinter
from pathlib import Path
from road_integer_common import ROOT,FLOAT,LIGHT,BASE,read,write,sha
from prepare_road_lcd_static import ROOT as LCD
HERE=Path(__file__).resolve().parent
PACK=Path('E:/FPGA_Enhance_Work/road_q8_board_candidate_20261027')

def main():
    app=ROOT/'m125/arm_lcd_r1';assert read(app/'offline_complete.json')['board_run'] is False
    shutil.copytree(app,PACK,ignore=shutil.ignore_patterns('obj','kernel_assembly.txt','build.log','road_lcd.map'))
    shutil.copy2(FLOAT/'graph.json',PACK/'graph.json');shutil.copy2(FLOAT/'YOLOv5_LICENSE',PACK/'YOLOv5_LICENSE')
    for name in ['protocol.json','prepare_complete.json']:shutil.copy2(ROOT/name,PACK/('quant_'+name))
    shutil.copy2(ROOT/'m125/quant_graph.json',PACK/'quant_graph.json')
    shutil.copy2(ROOT/'m125/host_complete.json',PACK/'host_numerical_proof.json');shutil.copy2(ROOT/'m125/fast_r1/complete.json',PACK/'exact_search_and_host_timing.json')
    shutil.copy2(ROOT/'c_validation320/complete.json',PACK/'actual_c_validation320.json')
    formats=[];g=read(FLOAT/'graph.json')
    for t in g['tensors']:
        formats.append(dict(id=t['id'],h=t['h'],w=t['w'],channels=t['c'],padded_channels=t['c4'],dtype='float32' if t['id'] in g['heads'] else 'uint8' if t['id']==0 else 'int8',
           file_suffix_note='Historical .f32 suffix is retained for harness compatibility; use this dtype, not suffix.',bytes=t['elements']*(4 if t['id'] in g['heads'] else 1)))
    write(PACK/'trace_formats.json',formats)
    for fixture in read(FLOAT/'export_complete.json')['fixtures']:
        name=fixture['name'];dest=PACK/'golden'/name;dest.mkdir(parents=True);shutil.copytree(ROOT/'m125/host'/name/'trace',dest/'trace')
        for file in ['input320.rgb','decoded.f32','boxes320.f32','boxes400.f32']:shutil.copy2(ROOT/'m125/host'/name/file,dest/file)
    # Self-contained validator: NumPy + stdlib only; all paths relative to this package.
    source=(HERE/'validate_road_q8_board.py').read_text()
    for line in ['from road_integer_common import ROOT,FLOAT,read,write,sha\n','from build_road_arm_probe import fnv\n','from verify_road_arm_host import compare_boxes\n']:source=source.replace(line,'')
    helpers='''import json,hashlib
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(data):
    value=2166136261
    for x in data:value=((value^x)*16777619)&0xffffffff
    return value
'''
    old=(HERE/'verify_road_arm_host.py').read_text();tree=ast.parse(old);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_boxes')
    helpers+='\n'.join(old.splitlines()[node.lineno-1:node.end_lineno])+'\n'
    source=source.replace('def validate(out,fixture):',helpers+'\ndef validate(out,fixture):')
    source=source.replace("app=ROOT/'m125/arm_lcd_r1';config=read(app/'offline_complete.json');g=read(FLOAT/'graph.json');out=Path(out);host=ROOT/'m125/host'/fixture", "app=ROOT;config=read(app/'offline_complete.json');g=read(app/'graph.json');out=Path(out);host=ROOT/'golden'/fixture")
    source=source.replace("raw=FLOAT/'cases'/fixture/'input400.u32'","raw=ROOT/'runtime/cases'/fixture/'input400.u32'")
    assert 'FLOAT' not in source and 'road_integer_common' not in source;compile(source,str(PACK/'validate_readback.py'),'exec');(PACK/'validate_readback.py').write_text(source,encoding='utf-8')
    # Existing actual FP32 readback must fail new ELF/model identity checks, with no files modified.
    namespace=runpy.run_path(str(PACK/'validate_readback.py'));oldreadback=LCD/'board_final_photo01';fixture=read(FLOAT/'export_complete.json')['fixtures'][0]['name']
    rejected=False
    try:namespace['validate'](oldreadback,fixture)
    except AssertionError:rejected=True
    assert rejected
    assert int(tkinter.Tcl().call('info','complete',(PACK/'install_ram.tcl').read_text()))==1
    (PACK/'README.md').write_text('''# 道路检测 Q8 候选包：尚未实板验收

仅在下一次开发板上电后进行 JTAG RAM 验证。本次未连接板卡，未写 SD 或 Flash。

检测类别：person、car、truck、bus。输入为400×240固定道路图片，网络输入320×320。画面不接摄像头，不启用增强支路。

## 当前计算分工

ARM Cortex-A9：预处理、W8/A8整数卷积、整数SiLU查表、Q20残差相加、FP32检测头解码/NMS、画框。PL沿用原来的显示硬件。没有新增FPGA CNN加速器，也不能把当前耗时称为实时视频帧率。

## 验证步骤

1. 板卡断电时设为此前已确认的JTAG启动方式，接好电源和下载器后上电。
2. 运行 `00_install_ram.cmd`。它做系统复位和PS初始化，只下载RAM程序/模型/固定图片；不写SD。
3. 必须看到 `ROAD_Q8_PHYSICAL_READBACK_COMPLETE`，并检查输出目录；XSCT进程退出码本身不足以证明成功。
4. 使用本机Python运行 `validate_readback.py 02e67bab-27594c1d 输出目录`。验证全部86层、三个检测头、解码、NMS、LCD帧缓冲和DMA状态。
5. 首张通过后再验证其余真实图片以及黑图、随机图，最后与原FP32版比较板上计时。主机SSE2计时不能预测ARM性能。

默认首张图片的主机输出为15个检测框；框数不等于真实物体数。若失败，不以“屏幕有框”代替数值验收。

## 可恢复版本

原FP32固定图片程序位于 `E:/FPGA_Enhance_Work/road_lcd_static_20261027/00_install_ram.cmd`，已完成前期实板与屏幕确认。本候选不会覆盖它。SD启动诊断是另一目录的未验收构建，不能把其BOOT.BIN当作已验证成品。

`source/` 是完整ARM候选源码；`runtime/model.bin` 是量化权重和查表数据；`golden/` 是主机参考输出，不是实板读回。`trace_formats.json` 给出每层实际字节类型，历史.f32后缀不代表内部A8数据为浮点。

YOLOv5相关代码和模型基于官方v7.0四类微调，保留GPL-3.0；见YOLOv5_LICENSE。道路样例来自此前固定的BDD100K资料镜像，详情见项目数据来源和清单。使用范围及数据许可沿用原项目记录。
''',encoding='utf-8')
    write(PACK/'package_preflight.json',dict(status='OFFLINE_CANDIDATE_PACKAGE_READY_NOT_BOARD_ACCEPTED',previous_physical_fp32_readback_rejected_as_new_firmware=True,
      tcl_syntax_complete=True,validator_self_contained=True,all_golden_outputs_are_host_only=True,board_accessed=False,sd_written=False))
    print('Q8_CANDIDATE_PACKAGE_PREPARED',str(PACK),flush=True)
if __name__=='__main__':main()
