"""Independently audit hook MACs with THOP configured to count Conv only."""
import os,sys
from pathlib import Path
from road_adapt_common import BASE,read,write,sha
from road_pipeline_diagnose import ROOT
os.chdir(BASE/'yolov5');sys.path.insert(0,str(BASE/'yolov5'))
import torch
from thop import profile
from thop.vision.basic_hooks import zero_ops
def main():
    torch.set_num_threads(4);budget=read(ROOT/'deployment_budget.json');result={}
    for size in [416,320,256]:
        model=torch.load(BASE/'frozen/road4_best.pt',map_location='cpu',weights_only=False)['model'].float().eval()
        mac,params=profile(model,inputs=(torch.zeros(1,3,size,size),),custom_ops={torch.nn.BatchNorm2d:zero_ops,torch.nn.Upsample:zero_ops,torch.nn.MaxPool2d:zero_ops},verbose=False)
        expected=budget['profiles'][str(size)]['conv_macs'];assert int(mac)==expected,(size,mac,expected)
        result[str(size)]=dict(hook_conv_mac=expected,independent_thop_conv_mac=int(mac),exact=True)
    bit=Path('E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/multinex_static.bit')
    current=read(Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026/offline_camera.json'))
    assert sha(bit)==current['bit_sha256']
    write(ROOT/'deployment_budget_check.json',dict(status='INDEPENDENT_MAC_PROFILE_EXACT_AND_CURRENT_APPLICATION_BIT_IDENTITY_CONFIRMED',profiles=result,
          source_bit_sha256=sha(bit),application_bit_sha256=current['bit_sha256'],no_hardware_read_or_write=True))
    print('ROAD_MAC_AND_BIT_IDENTITY_AUDIT_PASS',result,flush=True)
if __name__=='__main__':main()
