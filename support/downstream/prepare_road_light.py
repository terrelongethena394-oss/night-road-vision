"""Freeze actual-camera-order training data, narrow initializers and new holdout."""
from pathlib import Path
import collections,concurrent.futures as cf,copy,hashlib,os,shutil,sys
import cv2,numpy as np
from road_light_common import ROOT,BASE,TEACHER,TEACHER_SHA,NAMES,SEED,VARIANTS,EPOCHS,read,write,sha
from road_arm_common import preprocess400
def sensor_proxy(rgb):
    a=cv2.resize(rgb,(800,480),interpolation=cv2.INTER_LINEAR);a[:,:,0]&=248;a[:,:,1]&=252;a[:,:,2]&=248;b=a.astype(np.uint16)
    return ((b[0::2,0::2]+b[0::2,1::2]+b[1::2,0::2]+b[1::2,1::2]+2)//4).astype(np.uint8)
def initialize_models():
    import torch,yaml
    torch.set_num_threads(4);torch.manual_seed(SEED)
    os.chdir(ROOT/'yolov5');sys.path.insert(0,str(ROOT/'yolov5'))
    from models.yolo import Model,Detect
    from models.common import Conv,C3,Bottleneck,SPPF,Concat
    teacher=torch.load(TEACHER,map_location='cpu',weights_only=False)['model'].float().eval()
    for tag,width in VARIANTS.items():
        cfg=copy.deepcopy(teacher.yaml);cfg['width_multiple']=width;cfg['nc']=4;student=Model(cfg,ch=3,nc=4).float().eval();transfers=[]
        def conv(s,t,inmap,name):
            assert s.groups==t.groups==1 and s.kernel_size==t.kernel_size and len(inmap)==t.in_channels
            outputs=np.arange(t.out_channels);factor=float(np.sqrt(s.in_channels/t.in_channels))
            with torch.no_grad():
                t.weight.copy_(s.weight[outputs][:,inmap]*factor)
                if t.bias is not None:t.bias.copy_(s.bias[outputs])
            transfers.append(dict(name=name,old_shape=list(s.weight.shape),new_shape=list(t.weight.shape),input_channel_indices=list(map(int,inmap)),weight_scale=factor))
            return outputs.tolist(),s.out_channels
        def module(s,t,inmap,name):
            if isinstance(t,Conv):
                mapping,oldc=conv(s.conv,t.conv,inmap,name+'.conv')
                with torch.no_grad():
                    for attr in ['weight','bias','running_mean','running_var']:getattr(t.bn,attr).copy_(getattr(s.bn,attr)[mapping])
                    t.bn.num_batches_tracked.copy_(s.bn.num_batches_tracked)
                return mapping,oldc
            if isinstance(t,Bottleneck):
                y,_=module(s.cv1,t.cv1,inmap,name+'.cv1');z,oldc=module(s.cv2,t.cv2,y,name+'.cv2')
                if t.add:assert inmap==z
                return z,oldc
            if isinstance(t,C3):
                y,olda=module(s.cv1,t.cv1,inmap,name+'.cv1')
                assert len(s.m)==len(t.m)
                for j,(sb,tb) in enumerate(zip(s.m,t.m)):y,_=module(sb,tb,y,name+f'.m.{j}')
                z,_=module(s.cv2,t.cv2,inmap,name+'.cv2')
                return module(s.cv3,t.cv3,y+[olda+i for i in z],name+'.cv3')
            if isinstance(t,SPPF):
                y,oldc=module(s.cv1,t.cv1,inmap,name+'.cv1')
                return module(s.cv2,t.cv2,[i+k*oldc for k in range(4) for i in y],name+'.cv2')
            if isinstance(t,torch.nn.Upsample):return inmap,None
            raise TypeError(type(t))
        outputs=[];mapping=[0,1,2];oldc=3
        for s,t in zip(teacher.model,student.model):
            if t.f!=-1:
                if isinstance(t.f,int):mapping,oldc=outputs[t.f]
                else:
                    incoming=[(mapping,oldc) if j==-1 else outputs[j] for j in t.f];offset=0;mapping=[]
                    if isinstance(t,Concat):
                        for indices,count in incoming:mapping.extend(offset+i for i in indices);offset+=count
                        oldc=offset
                    else:mapping=incoming
            if isinstance(t,Detect):
                for j,(sc,tc,(indices,oldchannels)) in enumerate(zip(s.m,t.m,mapping)):conv(sc,tc,indices,f'model.{t.i}.m.{j}')
                with torch.no_grad():t.anchors.copy_(s.anchors)
                assert torch.equal(t.stride,s.stride);break
            if isinstance(t,Concat):pass
            elif isinstance(t,torch.nn.Upsample):pass
            else:mapping,oldc=module(s,t,mapping,f'model.{t.i}')
            outputs.append((list(mapping),oldc))
        student.names=NAMES;student.nc=4
        conv_macs=[];hooks=[]
        for m in student.modules():
            if isinstance(m,torch.nn.Conv2d):hooks.append(m.register_forward_hook(lambda layer,args,y:conv_macs.append(y.numel()*(layer.in_channels//layer.groups)*layer.kernel_size[0]*layer.kernel_size[1])))
        with torch.inference_mode():pred=student(torch.zeros(1,3,320,320))[0]
        for h in hooks:h.remove()
        assert list(pred.shape)==[1,6300,9] and torch.isfinite(pred).all()
        folder=ROOT/'initialization'/tag;folder.mkdir(parents=True)
        torch.save(dict(epoch=-1,best_fitness=0.,model=student.half(),ema=None,updates=0,optimizer=None,opt={},git={},date='2026-10-27'),folder/'initial.pt')
        (folder/'model.yaml').write_text(yaml.safe_dump(cfg),encoding='utf-8')
        write(folder/'proof.json',dict(status='STRUCTURED_CHANNEL_SLICE_INITIALIZED_NOT_FORWARD_EQUIVALENT_TO_TEACHER',width_multiple=width,
              parameters=sum(p.numel() for p in student.parameters()),conv_macs320=sum(conv_macs),source_sha256=TEACHER_SHA,initial_sha256=sha(folder/'initial.pt'),
              transfer=transfers,important='Concat branches mapped with original offsets. BN prefix stats inherited. Input fan-in sqrt compensation is initialization only, not an equivalence or accuracy claim.'))
        print('LIGHT_MODEL_INITIALIZED',tag,sum(p.numel() for p in student.parameters()),sum(conv_macs),flush=True)
def main():
    ROOT.mkdir(exist_ok=False);assert sha(TEACHER)==TEACHER_SHA
    old=read(BASE/'dataset/manifest.json');previous=read(Path('E:/FPGA_Enhance_Work/road_joint_adapt_20261026/fresh/manifest.json'))
    excluded={r['group'] for r in old+previous};names={r['name'] for r in old+previous};meta=[]
    for p in sorted((BASE/'source_metadata').glob('val_*.jsonl')):meta.extend(__import__('json').loads(s) for s in p.read_text().splitlines())
    paths={Path(x['rfilename']).name:x['rfilename'] for x in read(BASE/'BDD100K_repo.json')['siblings'] if x['rfilename'].endswith('.jpg') and '/val/' in x['rfilename']}
    selected=[];groups=set()
    for period,n in [('night',240),('dawn/dusk',96),('daytime',144)]:
        pool=[r for r in meta if r['label']==period and r['file_name'] in paths and r['file_name'].split('-')[0] not in excluded]
        pool.sort(key=lambda r:hashlib.sha256((str(SEED)+'|'+r['file_name']).encode()).hexdigest());count=0
        for r in pool:
            name=r['file_name'];group=name.split('-')[0]
            if group in groups:continue
            assert name not in names
            selected.append(dict(name=name,group=group,timeofday=period,image_path=paths[name],split='fresh_test',official_split='val'));groups.add(group);count+=1
            if count==n:break
        assert count==n
    write(ROOT/'fresh_selection.json',selected)
    write(ROOT/'protocol.json',dict(status='FROZEN_BEFORE_LIGHT_TRAINING_AND_NEW_TEST_INFERENCE',seed=SEED,teacher_sha256=TEACHER_SHA,variants=VARIANTS,
       epochs=EPOCHS,imgsz=320,batch16=True,train=2400,val=320,fresh_test=480,
       inputs='Sensor proxy resize800x480 RGB565 before2x2 rounded mean to400x240, then exact C integer bilinear320x192 plus64 gray padding. Labels map y=.6*y+.2,h=.6*h.',
       selection='Validation only. Compare teacher under same inputs. Candidate needs nightAP50>=.85*teacher, night-person recall>=.8*teacher, allAP50>=teacher-.03, night totalFP<=1.25*teacher+5 and personFP<=1.2*teacher+2. Prefer smallest ConvMAC among passing variants, then highest nightAP. Medium fallback allowed; if none pass record failure and retain teacher.',
       checkpoint_search='Per variant best plus every10epoch checkpoints, all on old validation only. Freeze selected weights before fresh holdout.',
       fresh_rule='New480 official-val filename-prefix groups exclude all previous3680 image groups; one image per new prefix. Exact image hashes checked after download.',
       no_hardware_access=True,no_sd_write=True))
    shutil.copytree(BASE/'yolov5',ROOT/'yolov5',ignore=shutil.ignore_patterns('__pycache__','runs','*.pyc','*.pt','.git'))
    p=ROOT/'yolov5/train.py';s=p.read_text(encoding='utf-8');needle='loss, loss_items = compute_loss(pred, targets.to(device))';assert s.count(needle)==1
    before=sha(p);p.write_text(s.replace(needle,'loss, loss_items = compute_loss(pred, targets.to(device), images=imgs)'),encoding='utf-8')
    write(ROOT/'training_source_patch.json',dict(file='train.py',before=before,after=sha(p),change='Pass current augmented image tensor to runtime distillation loss; validation calls without images remain supervised only.'))
    for split in ['train','val']:
        for sub in ['images','labels']:(ROOT/'dataset'/sub/split).mkdir(parents=True)
        (ROOT/'raw400'/split).mkdir(parents=True)
    rows=[r for r in old if r['status']=='READY' and r['split'] in ['train','val']]
    def one(r):
        split,name=r['split'],r['name'];stem=Path(name).stem;ip=BASE/'dataset/images'/split/name;assert sha(ip)==r['image_sha256']
        raw=sensor_proxy(cv2.imread(str(ip))[:,:,::-1]);im=preprocess400(raw)
        rp=ROOT/'raw400'/split/(stem+'.png');dp=ROOT/'dataset/images'/split/(stem+'.png')
        assert cv2.imwrite(str(rp),raw[:,:,::-1]) and cv2.imwrite(str(dp),im[:,:,::-1])
        original=(BASE/'dataset/labels'/split/(stem+'.txt')).read_text();lines=[]
        for line in original.splitlines():
            if not line:continue
            k,x,y,w,h=map(float,line.split());lines.append(f'{int(k)} {x:.9f} {(.6*y+.2):.9f} {w:.9f} {(.6*h):.9f}')
        lp=ROOT/'dataset/labels'/split/(stem+'.txt');lp.write_text('\n'.join(lines)+'\n' if lines else '',encoding='ascii')
        return {**r,'raw400_sha256':sha(rp),'input320_sha256':sha(dp),'mapped_label_sha256':sha(lp)}
    manifest=[]
    with cf.ThreadPoolExecutor(4) as pool:
        for r in pool.map(one,rows):
            manifest.append(r)
            if len(manifest)%400==0:print('LIGHT_CAMERA_INPUTS_READY',len(manifest),len(rows),flush=True)
    write(ROOT/'dataset/manifest.json',manifest)
    (ROOT/'dataset/road4.yaml').write_text('path: '+(ROOT/'dataset').as_posix()+'\ntrain: images/train\nval: images/val\nnc:4\nnames: [person, car, truck, bus]\n'.replace('nc:4','nc: 4'),encoding='ascii')
    initialize_models();write(ROOT/'prepare_complete.json',dict(status='LIGHT_TRAIN_DATA_AND_THREE_INITIALIZERS_READY',train=2400,val=320,dataset_manifest_sha256=sha(ROOT/'dataset/manifest.json'),fresh_selection_sha256=sha(ROOT/'fresh_selection.json')))
    print('LIGHT_PREPARATION_COMPLETE',flush=True)
if __name__=='__main__':main()
