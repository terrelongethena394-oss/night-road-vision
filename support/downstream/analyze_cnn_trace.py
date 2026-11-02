from pathlib import Path
import json
import numpy as np
from train_real_digit_cnn import OUT
from digit_model import rshift

def main():
    root=OUT/'layer_trace/trace_project/solution'
    raw=(root/'sim/wrapc_pc/trace_actual.txt').read_text().split()
    # RTL post-check output overwrites this file only in wrapc_pc.
    actual=[];at=0
    for case in range(3):
        assert int(raw[at])==case;at+=3
        actual.append(np.array(raw[at:at+3179],np.int64));at+=3179
    w=np.load(OUT/'integer_weights.npz')
    summaries=[]
    for i,a in enumerate(actual):
        x=a[:784].reshape(1,1,28,28)
        win=np.lib.stride_tricks.sliding_window_view(np.pad(x,((0,0),(0,0),(1,1),(1,1))),(3,3),axis=(2,3))
        z=np.clip(rshift(np.einsum('nchwkl,ockl->nohw',win,w['conv1.weight'],optimize=True)+w['conv1.bias'][None,:,None,None],12),0,1048575)
        shaped=z.reshape(1,8,14,2,14,2)
        ref=shaped.max((3,5));rtl=a[784:2352].reshape(ref.shape)
        probes={'correct_max':ref,'last':shaped[:,:,:,1,:,1],'first':shaped[:,:,:,0,:,0],
            'last_row_max':shaped[:,:,:,1,:,:].max(4),'last_col_max':shaped[:,:,:,:,:,1].max(3)}
        mismatch={key:int((value!=rtl).sum()) for key,value in probes.items()}
        positions=np.argwhere(ref!=rtl)
        row=dict(case=i,pool1_alternatives=mismatch,
            differences=[dict(channel=int(p[1]),y=int(p[2]),x=int(p[3]),expected=int(ref[tuple(p)]),actual=int(rtl[tuple(p)])) for p in positions[:40]])
        summaries.append(row);print(json.dumps(row),flush=True)
    (OUT/'layer_trace_analysis.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')

if __name__=='__main__':main()
