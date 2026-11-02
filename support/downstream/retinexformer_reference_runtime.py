"""Original-author Retinexformer as a PC reference, never claimed to run in PL."""
from pathlib import Path
import importlib.util,json,hashlib,time
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/retinexformer_reference_20261031_r1')
class Reference:
    def __init__(self):
        import torch
        self.t=torch;torch.set_num_threads(4)
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.allow_tf32=False
        torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
        meta=json.loads((ROOT/'source_manifest.json').read_text())
        src=ROOT/'source/basicsr/models/archs/RetinexFormer_arch.py'
        assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['files']['basicsr/models/archs/RetinexFormer_arch.py']['sha256']
        spec=importlib.util.spec_from_file_location('reviewed_retinexformer_arch',src)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        w=ROOT/'LOL_v1.pth';wm=json.loads((ROOT/'weight_manifest.json').read_text())
        assert hashlib.sha256(w.read_bytes()).hexdigest()==wm['sha256']
        checkpoint=torch.load(w,map_location='cpu',weights_only=True)
        print('RETINEXFORMER_CHECKPOINT_KEYS',list(checkpoint),flush=True)
        state=checkpoint['params'];self.net=module.RetinexFormer(stage=1,n_feat=40,num_blocks=[1,2,2])
        self.net.load_state_dict(state,strict=True);self.net.cuda().eval()
        self.parameters=sum(p.numel() for p in self.net.parameters())
    def run(self,a):
        assert a.dtype==np.uint8 and a.shape==(240,400,3)
        t=self.t;x=t.from_numpy(np.ascontiguousarray(a.transpose(2,0,1))).unsqueeze(0).cuda().float()/255
        with t.inference_mode():z=self.net(x).clamp(0,1)
        out=z[0].permute(1,2,0).cpu().numpy()
        return np.floor(out*255+.5).astype(np.uint8)
