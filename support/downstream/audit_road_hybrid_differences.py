"""Audit frozen readbacks against both host reference and previously validated ARM data."""
from pathlib import Path
import json,numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
def compare(p,q):
    a=np.fromfile(p,'<f4');b=np.fromfile(q,'<f4');assert a.shape==b.shape
    d=abs(a-b)
    return dict(bytes_exact=p.read_bytes()==q.read_bytes(),max_abs=float(d.max()) if len(d) else 0,bad_previous_tolerance=int(np.count_nonzero(d>1e-4+1e-4*abs(b))),finite=bool(np.isfinite(a).all()),elements=len(a))
def main():
    report={};first='02e67bab-27594c1d';gold=NN/'host_r2'/first
    for name in ['cpu_first',first]:
        base=ROOT/'physical_full_r1'/name;rows=[]
        for j,node in enumerate([83,84,85]):rows.append(dict(head=node,**compare(base/f'head{j}.f32',gold/'trace'/f'{node:03d}.f32')))
        report[name]=rows
    prior=[]
    for folder in CAM.glob('board*'):
        if (folder/'context.txt').exists() and ('fixture='+first) in (folder/'context.txt').read_text():
            prior.append(dict(folder=str(folder),head_vs_host=compare(folder/'head0.f32',gold/'trace/083.f32'),new_cpu_vs_prior_arm=compare(ROOT/'physical_full_r1/cpu_first/head0.f32',folder/'head0.f32')))
    report['previously_validated_arm']=prior
    report['cpu_vs_hybrid']=[dict(head=j,**compare(ROOT/'physical_full_r1/cpu_first'/f'head{j}.f32',ROOT/'physical_full_r1'/first/f'head{j}.f32')) for j in range(3)]
    report['all8_against_prior_arm']=[]
    for f in json.loads((NN/'export_complete.json').read_text())['fixtures']:
        folder=ROOT/'physical_full_r1'/f['name'];prior=NN/'board_batch_r2'/f['name']
        report['all8_against_prior_arm'].append(dict(name=f['name'],files={name:compare(folder/name,prior/name) for name in ['head0.f32','head1.f32','head2.f32','decoded.f32','boxes400.f32']}))
    report['full86_vs_prior_arm']=compare(ROOT/'physical_full_r1/first_hybrid_full/all_layers.f32',CAM/'board_fixed_first/all_layers.f32')
    (ROOT/'difference_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
