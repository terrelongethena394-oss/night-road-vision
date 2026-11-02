"""Use the existing isolated CUDA torch and detector dependencies."""
from pathlib import Path
import os,runpy,sys

sys.path[:0]=['E:/FPGA_Enhance_Work/plate_gpu_lib','E:/FPGA_Enhance_Work/road_detector_lib']
os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_DISABLED='true',COMET_MODE='DISABLED')
import torch
assert torch.cuda.is_available(),torch.__version__
print('ROAD_CUDA_RUNTIME',torch.__version__,torch.cuda.get_device_name(0),flush=True)
task=Path(sys.argv[1]).resolve();sys.argv=sys.argv[1:]
sys.path.insert(0,str(task.parent));runpy.run_path(str(task),run_name='__main__')
