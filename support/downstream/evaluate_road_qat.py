"""Exact integer export/evaluation of only the two predeclared QAT checkpoints."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,subprocess,sys,time
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
OLD=Path('E:/FPGA_Enhance_Work/road_integer_20261027')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2),encoding='utf-8')
def main():
    assert (ROOT/'protocol.json').exists();exports=ROOT/'exports';exports.mkdir(exist_ok=False)
    source=(HERE/'prepare_road_integer.py').read_text()
    source=source.replace('from road_integer_common import ROOT,FLOAT,LIGHT,MARGINS,read,write,sha','from road_integer_common import FLOAT,LIGHT,MARGINS,read,write,sha\nROOT=Path("E:/FPGA_Enhance_Work/road_realtime_20261027/exports")\nFIXED_ARRAYS=np.load("E:/FPGA_Enhance_Work/road_integer_20261027/m125/quant_arrays.npz")\nSOURCE_WEIGHTS_SHA=""')
    old='ws=np.maximum(np.abs(eff).max((0,1,2))/127,1e-12).astype(np.float32)';assert source.count(old)==1
    source=source.replace(old,"ws=FIXED_ARRAYS[f'ws_{i}'].copy()")
    source=source.replace("source_weights_sha256=sha(FLOAT/'weights.f32')","source_weights_sha256=SOURCE_WEIGHTS_SHA")
    module_path=ROOT/'source/fixed_scale_export.py';module_path.write_text(source,encoding='utf-8')
    spec=importlib.util.spec_from_file_location('fixed_scale_export',module_path);export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
    g=json.loads((NN/'graph.json').read_text());maxima=np.load(OLD/'calibration_maxima.npz');base=np.fromfile(NN/'weights.f32','<f4')
    export.SOURCE_WEIGHTS_SHA=sha(NN/'weights.f32');export.export_variant('initial',1.25,g,base,maxima)
    assert (exports/'initial/qmodel.bin').read_bytes()==(OLD/'m125/qmodel.bin').read_bytes(),'Initial fixed-scale exporter must reproduce known integer model'
    write(ROOT/'fixed_export_identity.json',dict(status='INITIAL_QMODEL_BINARY_BYTES_EXACT_TO_PRIOR_M125',old_model_sha256=sha(OLD/'m125/qmodel.bin'),new_model_sha256=sha(exports/'initial/qmodel.bin'),source_sha256=sha(module_path),hardware_access=False))
    from road_integer_reference import evaluate
    from road_light_evaluate import validation_rows,validation_loader
    teacher=json.loads(Path('E:/FPGA_Enhance_Work/road_light_20261027/baseline/complete.json').read_text())['metrics']
    records=[];began=time.monotonic()
    for epoch in [4,8]:
        checkpoint=ROOT/f'epoch{epoch}'
        while not (checkpoint/'frozen.json').exists():
            if time.monotonic()-began>7200:raise TimeoutError('QAT checkpoint did not finish')
            time.sleep(2)
        frozen=json.loads((checkpoint/'frozen.json').read_text());weights=checkpoint/'qat_fused_weights.f32';assert sha(weights)==frozen['weights_sha256']
        export.SOURCE_WEIGHTS_SHA=sha(weights);tag=f'epoch{epoch}';export.export_variant(tag,1.25,g,np.fromfile(weights,'<f4'),maxima)
        out=ROOT/f'validation_{tag}';out.mkdir()
        metrics=evaluate(exports/tag,validation_rows(),validation_loader,out,tag)
        night=metrics['by_time']['night'];base_night=teacher['by_time']['night'];p=night['classes']['person'];bp=base_night['classes']['person']
        tests=dict(night_ap=night['mAP50']>=.95*base_night['mAP50'],all_ap=metrics['all']['mAP50']>=.97*teacher['all']['mAP50'],person_recall=p['recall']>=.9*bp['recall'],night_fp=sum(c['fp'] for c in night['classes'].values())<=1.1*sum(c['fp'] for c in base_night['classes'].values())+2,person_fp=p['fp']<=1.1*bp['fp']+2)
        r=dict(epoch=epoch,metrics=metrics,gates=tests,passed=all(tests.values()),qmodel_sha256=sha(exports/tag/'qmodel.bin'),source_frozen_sha256=sha(checkpoint/'frozen.json'))
        write(out/'complete.json',r);records.append(r);print('ROAD_QAT_EXACT_VALIDATION_COMPLETE',epoch,night['mAP50'],tests,flush=True)
    passing=[r for r in records if r['passed']];selected=max(passing,key=lambda r:r['metrics']['by_time']['night']['mAP50']) if passing else None
    write(ROOT/'selection_complete.json',dict(status='QAT_OLD_VALIDATION_ONLY_SELECTION_COMPLETE',records=records,selected_epoch=selected['epoch'] if selected else None,selected_qmodel_sha256=selected['qmodel_sha256'] if selected else None,selected_frozen_before_new_holdout=True,hardware_access=False,sd_written=False,current_deployed_model_replaced=False))
    print('ROAD_QAT_SELECTION_FINISHED',selected['epoch'] if selected else 'NONE_RETAIN_CURRENT_FP32',flush=True)
if __name__=='__main__':main()
