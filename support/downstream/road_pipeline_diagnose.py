"""Frozen validation-only arithmetic/input-format diagnosis and deployment budget."""
from pathlib import Path
import collections,copy,importlib.util,os,re,sys,time
import cv2,numpy as np
from road_adapt_common import BASE,ROOT as ROUND2,NAMES,read,write,sha,canonical,luma
ROOT=Path('E:/FPGA_Enhance_Work/road_pipeline_diagnostic_20261026')
GOLD=Path('E:/FPGA_Enhance_Work/enhancement_study_20261025/multinex_port_candidate')
NN=Path(__file__).resolve().parent.parent/'nn'

def load_float():
    import torch
    spec=importlib.util.spec_from_file_location('diagnostic_multinex_official',GOLD/'MultinexNano_arch.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=read(GOLD/'architecture_config.json')['official_config'];model=module.MultinexNano(**config).eval()
    state=torch.load(GOLD/'official_reference.pth',map_location='cpu',weights_only=True)
    model.load_state_dict(state.get('params',state))
    folded=copy.deepcopy(model)
    for branch in ['illum_mid_seq','chroma_mid_seq']:
        block=getattr(folded,branch)[0][0]
        block.pw=torch.nn.utils.fusion.fuse_conv_bn_eval(block.pw,block.bn);block.bn=torch.nn.Identity()
    folded.load_state_dict(torch.load(GOLD/'folded_reference.pth',map_location='cpu',weights_only=True))
    return model,folded

def epsilon_audit(model):
    config=read(GOLD/'architecture_config.json')['official_config']
    audit=dict(status='ACTUAL_EXECUTION_EPSILON_MATCHES_FIXED_REFERENCE',config_eps=config['eps'],top_level_model_eps=model.eps,
          actual_illum_extractor_eps=model.illum_extractor.eps,actual_chroma_extractor_eps=model.chroma_extractor.eps,
          fixed_reference_eps=1e-6,explanation='Official constructor stores top-level eps but constructs extractors without forwarding it. Both extractors retain default1e-6. eps1e6 view is therefore an identity control, not a repair.')
    assert model.illum_extractor.eps==model.chroma_extractor.eps==1e-6
    write(ROOT/'epsilon_execution_audit.json',audit)
    return audit

def model_budget(weights):
    import torch
    model=torch.load(weights,map_location='cpu',weights_only=False)['model'].float().eval();parameters=sum(p.numel() for p in model.parameters())
    profiles={}
    for size in [416,320,256]:
        rows=[];top=[];hooks=[]
        for name,m in model.named_modules():
            if isinstance(m,torch.nn.Conv2d):
                def hook(module,inputs,out,name=name):
                    mac=out.numel()*(module.in_channels//module.groups)*module.kernel_size[0]*module.kernel_size[1]
                    rows.append(dict(name=name,shape=list(out.shape),macs=mac,output_elements=out.numel(),kernel=list(module.kernel_size),stride=list(module.stride),groups=module.groups))
                hooks.append(m.register_forward_hook(hook))
        def elements(v):
            if torch.is_tensor(v):return v.numel()
            if isinstance(v,(list,tuple)):return sum(elements(x) for x in v)
            return 0
        for m in model.model:
            def record(module,inputs,out):top.append(dict(index=module.i,from_index=module.f,type=module.type,output_elements=elements(out)))
            hooks.append(m.register_forward_hook(record))
        with torch.inference_mode():model(torch.zeros(1,3,size,size))
        for h in hooks:h.remove()
        profiles[str(size)]=dict(conv_macs=sum(r['macs'] for r in rows),conv_flops_at_2_per_mac=2*sum(r['macs'] for r in rows),
              largest_conv_activation_elements=max(r['output_elements'] for r in rows),top_level_output_elements_sum=sum(r['output_elements'] for r in top),
              convs=rows,top_level_graph=top,
              note='Conv/linear MAC count only. Activation counts omit layer-internal temporaries and are not actual peak memory or bandwidth. No board timing measured.')
    report=Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/utilization.rpt')
    text=report.read_text();resources={}
    for label in ['Slice LUTs','Slice Registers','Slice','Block RAM Tile','DSPs']:
        match=re.search(r'^\| '+re.escape(label)+r'\s+\|\s*(\d+)\s*\|\s*\d+\s*\|\s*(\d+)\s*\|',text,re.M)
        assert match,label
        used,total=map(int,match.groups());resources[label]=dict(used=used,total=total,remaining=total-used,percent=100*used/total)
    for p in profiles.values():
        p['illustrative_compute_only_ms_57DSP_100MHz_1MAC_per_DSP_cycle']=p['conv_macs']/(57*100e6)*1000
        p['illustrative_compute_only_ms_220DSP_100MHz_1MAC_per_DSP_cycle']=p['conv_macs']/(220*100e6)*1000
    write(ROOT/'deployment_budget.json',dict(status='HOST_GRAPH_PROFILE_AND_EXISTING_ROUTED_RESOURCE_AUDIT_NOT_A_BOARD_RUNTIME',parameters=parameters,
          parameter_storage_bytes=dict(fp32=4*parameters,fp16=2*parameters,int8_ideal=parameters),profiles=profiles,existing_resources=resources,
          routed_report=str(report),routed_report_sha256=sha(report),current_application='Vitis standalone arm-none-eabi cortex-a9 NEON, not Linux userspace',
          budget_caveats=['DSP compute examples assume 1 MAC per DSP each100MHz cycle and100% utilization, exclude transfers/SiLU/NMS. Packing, scheduling and bitwidth change these figures; not universal bounds or FPS.',
                         'Unused resource counts do not guarantee new placement/routing. Existing routed Slice occupancy is very high.',
                         'INT8 parameter-size estimate does not prove calibrated full INT8 accuracy or executable model.'],board_deployed=False,sd_written=False))

def main():
    ROOT.mkdir(exist_ok=True);assert not (ROOT/'complete.json').exists();start=time.monotonic()
    rows=[{**r,'label_path':str(BASE/'dataset/labels/val'/(Path(r['name']).stem+'.txt'))} for r in read(ROUND2/'paired_manifest.json') if r['split']=='val']
    assert len(rows)==320 and all(r['split']=='val' for r in rows)
    selected=[r['name'] for period,n in [('night',3),('dawn/dusk',2),('daytime',1)] for r in [x for x in rows if x['timeofday']==period][:n]]
    weights=BASE/'frozen/road4_best.pt'
    assert sha(weights)=='98f46429cd431d735e276d7735f50f61811a70cbb5feb2a0475fba562449a46f'
    gold=read(GOLD/'golden_status.json')
    assert sha(GOLD/'official_reference.pth')==gold['weights_sha256'] and sha(GOLD/'folded_reference.pth')==gold['folded_sha256']
    protocol=dict(status='FROZEN_BEFORE_DIAGNOSTIC_INFERENCE',split='Existing320validation, diagnostic only; not a new independent test',
         rows=[dict(name=r['name'],group=r['group'],timeofday=r['timeofday']) for r in rows],examples=selected,weights_sha256=sha(weights),
         float_original_sha256=sha(GOLD/'official_reference.pth'),float_folded_sha256=sha(GOLD/'folded_reference.pth'),
         views=['raw888','raw565','float888','float565','fixed565','float565_eps1e6'],detector_sizes=[416,320,256],
         precision_experiment='Raw565 at320/256 with per-output-channel symmetric INT8 Conv weights dequantized into float16; no activation quantization or ARM runtime claim.',
         no_training=True,no_test_split_used=True,board_modified=False,sd_written=False)
    if (ROOT/'protocol.json').exists():assert read(ROOT/'protocol.json')==protocol
    else:write(ROOT/'protocol.json',protocol)
    import torch
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    original,folded=load_float();epsilon_audit(original);original=original.cuda();folded=folded.cuda();modified=copy.deepcopy(original)
    modified.illum_extractor.eps=1e-6;modified.chroma_extractor.eps=1e-6
    frames=ROOT/'frames';frames.mkdir();quality=[]
    def infer(m,a):
        x=torch.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).cuda().float()[None]/255
        with torch.inference_mode():y=m(x)[0].permute(1,2,0)
        return y.cpu().numpy()
    fold_errors=[]
    for index,r in enumerate(rows,1):
        stem=Path(r['name']).stem;image=BASE/'dataset/images/val'/r['name'];assert sha(image)==r['image_sha256']
        rgb=cv2.imread(str(image))[:,:,::-1];raw888=cv2.resize(rgb,(400,240),interpolation=cv2.INTER_LINEAR);raw565=canonical(rgb)
        prepared=cv2.imread(str(ROUND2/'frames/val/raw'/(stem+'.png')))[:,:,::-1];assert np.array_equal(prepared,raw565)
        fixed=cv2.imread(str(ROUND2/'frames/val/net'/(stem+'.png')))[:,:,::-1]
        assert sha(ROUND2/'frames/val/net'/(stem+'.png'))==r['net_sha256']
        float565=infer(original,raw565);fold565=infer(folded,raw565);err=float(np.abs(float565-fold565).max());assert err<1e-3
        fold_errors.append(err)
        def u8(a):return np.floor(np.clip(a,0,1)*255+.5).astype(np.uint8)
        data=dict(raw888=raw888,raw565=raw565,float888=u8(infer(original,raw888)),float565=u8(float565),fixed565=fixed,float565_eps1e6=u8(infer(modified,raw565)))
        item=dict(name=r['name'],timeofday=r['timeofday'],float_fold_max_error=err,pairs={},views={})
        for kind,a in data.items():
            assert cv2.imwrite(str(frames/(stem+'.'+kind+'.png')),a[:,:,::-1])
            y=luma(a);item['views'][kind]=dict(mean_luma=float(y.mean()),zero_pixel_fraction=float((a.max(2)==0).mean()),
                any_channel_255_fraction=float((a.max(2)==255).mean()),all_channel_255_fraction=float((a.min(2)==255).mean()),
                luma_250_fraction=float((y>=250).mean()),unique_rgb_colors=int(len(np.unique(a.reshape(-1,3),axis=0))))
        for a,b in [('fixed565','float565'),('float565_eps1e6','float565'),('raw565','raw888'),('float565','float888')]:
            difference=np.abs(data[a].astype(np.int16)-data[b].astype(np.int16));item['pairs'][a+'__'+b]=dict(mae=float(difference.mean()),max_abs=int(difference.max()),
                  pixels_any_channel_diff=float(np.any(difference>0,2).mean()),pixels_any_channel_diff_gt2=float(np.any(difference>2,2).mean()))
        quality.append(item)
        if index%40==0:print('DIAGNOSTIC_FLOAT_VIEWS_READY',index,len(rows),flush=True)
    del original,folded,modified;torch.cuda.empty_cache()
    write(ROOT/'pixel_diagnostics.json',dict(status='SAME_WEIGHT_SAME_INPUT_FLOAT_VS_FIXED_CHECK',images=quality,max_float_fold_error=max(fold_errors),
          no_paired_bright_ground_truth=True,note='Clipping/color counts are diagnostics, not perceptual-quality ground truth or PSNR/SSIM quality claims.'))
    # Exact evaluator parity on old validation-selected candidate before using size extension.
    from road_adapt_eval_core import Evaluator
    from road_pipeline_eval import PipelineEvaluator,quantize_conv_weights
    folder=ROOT/'validation';folder.mkdir();load=lambda r,k:cv2.imread(str(frames/(Path(r['name']).stem+'.'+k+'.png')))[:,:,::-1].copy()
    legacy=Evaluator(ROUND2/'frozen/raw_control/best.pt');check=legacy.run(rows,lambda r:load(r,'raw565'),folder,'evaluator_control');legacy.close()
    known=read(ROUND2/'validation/raw_control__raw_metrics.json')
    assert check['all']==known['all'] and check['by_time']==known['by_time']
    evaluator=PipelineEvaluator(ROUND2/'frozen/raw_control/best.pt');again=evaluator.run(rows,lambda r:load(r,'raw565'),folder,'evaluator_extended_control');evaluator.close()
    assert again['all']==check['all'] and again['by_time']==check['by_time']
    a=read(folder/'evaluator_control_predictions.json');b=read(folder/'evaluator_extended_control_predictions.json');assert a==b
    write(ROOT/'evaluator_parity.json',dict(status='DEFAULT416_EXTENSION_AND_FROZEN_VALIDATION_PREDICTIONS_EXACT',images=320,predictions_exact=True,metrics_exact=True))
    scores={};evaluator=PipelineEvaluator(weights)
    for view in protocol['views']:scores[view+'_416']=evaluator.run(rows,lambda r,k=view:load(r,k),folder,view+'_416')
    for size in [320,256]:scores['raw565_'+str(size)]=evaluator.run(rows,lambda r:load(r,'raw565'),folder,'raw565_'+str(size),size)
    qproof=quantize_conv_weights(evaluator,ROOT/'weight_only_sensitivity.npz');write(ROOT/'weight_only_sensitivity.json',qproof)
    for size in [320,256]:scores['raw565_weight8sim_'+str(size)]=evaluator.run(rows,lambda r:load(r,'raw565'),folder,'raw565_weight8sim_'+str(size),size)
    evaluator.close();model_budget(weights)
    write(ROOT/'complete.json',dict(status='VALIDATION_ONLY_ENHANCEMENT_AND_DEPLOYMENT_DIAGNOSTIC_COMPLETE',seconds=time.monotonic()-start,scores=scores,
          protocol_sha256=sha(ROOT/'protocol.json'),no_test_split_used=True,weights_modified_on_disk=False,board_deployed=False,sd_written=False))
    print('ROAD_PIPELINE_DIAGNOSIS_COMPLETE',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
