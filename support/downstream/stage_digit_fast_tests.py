from pathlib import Path
import json,hashlib,shutil,re
import numpy as np
BASE=Path('E:/FPGA_Enhance_Work')
OLD=BASE/'multinex_camera_digit_20261026'
ROOT=BASE/'multinex_camera_digit_fast_20261026'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    shutil.copytree(OLD/'digit_inputs',ROOT/'digit_inputs',dirs_exist_ok=True)
    cases=json.loads((OLD/'digit_cases.json').read_text(encoding='utf-8'))
    lines=['set cases [list]']
    for c in cases:
        p=ROOT/'digit_inputs'/Path(c['file']).name;assert sha(p)==c['input_sha256'];c['file']=p.as_posix()
        x,y,s=c['roi'];lines.append(f'lappend cases [dict create id {c["id"]} file {{{c["file"]}}} fnv {c["input_fnv"]} x {x} y {y} size {s}]')
    (ROOT/'digit_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'digit_cases.tcl').write_text('\n'.join(lines)+'\n',encoding='ascii')
    q=np.load(BASE/'real_digit_training_20261025/cnn_candidate/integer_weights.npz');upper=np.array([255],np.int64);bounds=[]
    header=(ROOT/'app_src/cnn_weights.h').read_text('ascii')
    for key in q.files:
        name='CNN_'+key.upper().replace('.','_')
        body=re.search(r'\b'+name+r'\s*\[[^;=]*=\s*([^;]+);',header)[1]
        values=np.array(json.loads(body.replace('{','[').replace('}',']')),np.int64)
        assert np.array_equal(values,q[key]),name
    for name in ('conv1','conv2','fc1','fc2'):
        w=q[name+'.weight'].astype(np.int64);b=q[name+'.bias'].astype(np.int64)
        if name=='fc1':upper=np.repeat(upper,49)
        if name.startswith('conv'):
            product=np.abs(w)*upper[None,:,None,None]
            acc=product.sum((1,2,3))+np.abs(b)
            high=(np.maximum(w,0)*upper[None,:,None,None]).sum((1,2,3))+b
        else:
            product=np.abs(w)*upper
            acc=product.sum(1)+np.abs(b);high=np.maximum(w,0)@upper+b
        bound=int(acc.max());prod=int(product.max())
        assert max(bound,prod)<(1<<31 if name!='fc2' else 1<<39)
        bounds.append(dict(layer=name,absolute_accumulator_bound=bound,absolute_product_bound=prod,bits=32 if name!='fc2' else 64))
        upper=np.clip((np.maximum(high,0)+2048)>>12,0,1048575)
    (ROOT/'classifier_width_proof.json').write_text(json.dumps(dict(status='ALL_RGB8_ABSOLUTE_PARTIAL_SUM_BOUNDS',bounds=bounds,header_matches_bound_weights=True,
        reasoning='Absolute weighted sum plus absolute bias bounds every accumulation prefix as well as the final sum. All ReLU values nonnegative. FC2 product/total require64bits; no silent32bit truncation.'),indent=2),encoding='utf-8')
    print('FAST_TESTS_REBASED_AND_ABSOLUTE_BOUNDS_PROVED',flush=True)
if __name__=='__main__':main()
