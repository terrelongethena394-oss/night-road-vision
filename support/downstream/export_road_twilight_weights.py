"""Map the unchanged YOLO graph to the already verified C/FPGA weight ABI."""
from pathlib import Path
import copy,sys
import numpy as np
from road_twilight_common import ROOT,BASE,NN,TEACHER,TEACHER_SHA,sha,write,read
def pack(weights):
 import torch
 sys.path.insert(0,str(BASE/'yolov5'));model=torch.load(weights,map_location='cpu',weights_only=False)['model'].float().eval();model=copy.deepcopy(model).fuse().eval()
 g=read(NN/'graph.json');out=np.zeros(g['weights_floats'],dtype='<f4');shapes=[]
 for t in g['tensors'][1:]:
  if t['kind']!=1:continue
  if t['id'] in g['heads']:conv=model.model[-1].m[g['heads'].index(t['id'])]
  else:
   wrapper=model.get_submodule(t['name']);assert hasattr(wrapper,'conv') and isinstance(wrapper.act,torch.nn.SiLU);conv=wrapper.conv
  inp=g['tensors'][t['inputs'][0]];assert conv.groups==1 and conv.dilation==(1,1) and tuple(conv.kernel_size)==(t['k'],t['k']) and tuple(conv.stride)==(t['s'],t['s']) and tuple(conv.padding)==(t['p'],t['p'])
  assert conv.weight.shape==(t['c'],inp['c'],t['k'],t['k']) and conv.bias.shape==(t['c'],)
  values=np.zeros((t['k'],t['k'],inp['c4'],t['c4']),np.float32);values[:,:,:inp['c'],:t['c']]=conv.weight.detach().numpy().transpose(2,3,1,0)
  bias=np.zeros(t['c4'],np.float32);bias[:t['c']]=conv.bias.detach().numpy();out[t['woff']:t['woff']+values.size]=values.ravel();out[t['boff']:t['boff']+len(bias)]=bias
  shapes.append(dict(id=t['id'],module=t['name'],shape=list(conv.weight.shape)))
 head=model.model[-1];assert head.nc==4 and head.na==3 and head.nl==3
 assert np.array_equal(head.stride.detach().numpy(),np.asarray(g['strides'],np.float32))
 assert np.array_equal((head.anchors*head.stride[:,None,None]).detach().numpy(),np.asarray(g['anchors_pixels'],np.float32))
 assert np.isfinite(out).all();return model,g,out,shapes
def identity():
 outdir=ROOT/'export_identity';outdir.mkdir(exist_ok=True);assert not (outdir/'complete.json').exists();assert sha(TEACHER)==TEACHER_SHA
 model,g,out,shapes=pack(TEACHER);assert out.tobytes()==(NN/'weights.f32').read_bytes(),'Weight ABI exporter does not reproduce original baseline'
 write(outdir/'complete.json',dict(status='ALL60_WEIGHT_AND_BIAS_LAYOUTS_BYTES_EXACT_TO_EXISTING_C_FPGA_MODEL',source_checkpoint_sha256=TEACHER_SHA,binary_sha256=sha(NN/'weights.f32'),graph_sha256=sha(NN/'graph.json'),weight_floats=len(out),shapes=shapes,hardware_access=False));print('TWILIGHT_EXPORTER_ORIGINAL_BINARY_EXACT',flush=True)
if __name__=='__main__':identity()
