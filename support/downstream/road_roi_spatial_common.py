from road_roi_verifier_common import BASE,R2,GUARD,OLD,TEACHER,TEACHER_SHA,read,write,sha,person_eligible,crop_patch,verified_fuse
ROOT=BASE.parent/'road_roi_spatial_verifier_20261028'
SEED=2026102857
EPOCHS=80
CHECKPOINTS=[20,40,80]
FLOORS=[.5,.7,.85]

def make_model():
 import torch
 return torch.nn.Sequential(torch.nn.Conv2d(3,8,3,2,1),torch.nn.ReLU(),torch.nn.Conv2d(8,16,3,2,1),torch.nn.ReLU(),torch.nn.Conv2d(16,16,3,2,1),torch.nn.ReLU(),torch.nn.Flatten(),torch.nn.Linear(288,32),torch.nn.ReLU(),torch.nn.Linear(32,1))
