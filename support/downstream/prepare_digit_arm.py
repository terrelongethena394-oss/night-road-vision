"""Verify native classifier against independent frozen NumPy, no retraining."""
from pathlib import Path
import json,hashlib,shutil,subprocess,os,sys
import numpy as np
import torch
ROOT=Path('E:/FPGA_Enhance_Work/digit_arm_reference_20261026')
BASE=ROOT.parent
HERE=Path(__file__).resolve().parent
OLD=BASE/'real_digit_training_20261025/cnn_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    global ROOT
    narrow='i32' in sys.argv
    if narrow:ROOT=BASE/'digit_arm_reference_i32_20261026'
    ROOT.mkdir(exist_ok=True);assert not (ROOT/'complete.json').exists()
    model=OLD/'real_digit_cnn.pth';assert sha(model)=='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493'
    header=OLD/'hls_score64/cnn_weights.h'
    for p in (header,HERE/'digit_arm_kernel.h',HERE/'digit_arm_host.c'):shutil.copy2(p,ROOT/p.name)
    torch.set_num_threads(4)
    sys.path.insert(0,str(HERE))
    from train_real_digit_cnn import IntegerCNN,conservative_bounds
    q=IntegerCNN(torch.load(model,map_location='cpu',weights_only=True))
    bounds=conservative_bounds(q)
    if narrow:
        assert all(-(1<<31)<r['acc_min']<=r['acc_max']<(1<<31) for r in bounds[:3])
        assert all(np.all(v>=-(1<<31)) and np.all(v<(1<<31)) for k,v in q.s.items() if k.endswith('bias'))
    rng=np.random.default_rng(20261026)
    data=np.load(BASE/'real_digit_training_20261025/data/train_board_gray.npz')
    # Numerical regression inputs only; not a new accuracy benchmark or selection.
    x=data['x'];chosen=np.arange(0,min(len(x),600),3)
    inputs=np.concatenate([np.zeros((1,28,28),np.uint8),np.full((1,28,28),255,np.uint8),
        np.arange(784,dtype=np.uint16).reshape(1,28,28).astype(np.uint8),
        rng.integers(0,256,(16,28,28),dtype=np.uint8),x[chosen].astype(np.uint8).reshape(-1,28,28)])
    (ROOT/'gray28.bin').write_bytes(inputs.tobytes())
    predictions,expected=q.infer(inputs)
    (ROOT/'expected_scores.i64').write_bytes(expected.astype('<i8').tobytes())
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
    env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-static',str(ROOT/'digit_arm_host.c'),'-o',str(ROOT/'digit_arm_host.exe')]
    r=subprocess.run(cmd,capture_output=True,text=True,env=env);(ROOT/'compile.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr
    r=subprocess.run([str(ROOT/'digit_arm_host.exe'),str(ROOT/'gray28.bin'),str(ROOT/'actual_scores.i64')],capture_output=True,text=True);assert r.returncode==0,r.stderr
    actual=np.fromfile(ROOT/'actual_scores.i64',dtype='<i8').reshape(-1,11)
    assert np.array_equal(actual,expected)
    result=dict(status='NATIVE_C_NUMPY_ALL_LOGITS_EXACT',cases=len(inputs),logits=len(inputs)*11,
        model_sha256=sha(model),weights_header_sha256=sha(ROOT/'cnn_weights.h'),kernel_sha256=sha(ROOT/'digit_arm_kernel.h'),
        host_exe_sha256=sha(ROOT/'digit_arm_host.exe'),scores_sha256=sha(ROOT/'actual_scores.i64'),accumulator_bounds=bounds,
        note='Existing training examples and numeric controls used only to check arithmetic. No new recognition accuracy/generalization claim. Same original frozen model, not rejected preservation-trained candidate.')
    (ROOT/'complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('NATIVE_CNN_NUMERIC_PASS',len(inputs),len(inputs)*11,flush=True)
if __name__=='__main__':main()
