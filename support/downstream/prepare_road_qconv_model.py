"""Build/independently verify model packing. Quality failure is preserved, not promoted."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,subprocess
import numpy as np
ROOT=Path('E:/FPGA_Enhance_Work/road_realtime_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    selection=json.loads((ROOT/'selection_complete.json').read_text());epoch=selection['selected_epoch'];assert epoch is not None
    source=ROOT/'exports'/f'epoch{epoch}';assert (source/'host_complete.json').exists()
    out=ROOT/'hardware_model';out.mkdir(exist_ok=False);q=json.loads((source/'quant_graph.json').read_text());g=json.loads((NN/'graph.json').read_text());arrays=np.load(source/'quant_arrays.npz')
    shutil.copy2(HERE/'road_qconv_pack.c',out/'road_qconv_pack.c');env=os.environ.copy();env['PATH']=str(GCC.parent)+';'+env['PATH']
    cmd=[str(GCC),'-O3','-std=c99','-Wall','-Wextra','-Werror','-shared',str(out/'road_qconv_pack.c'),'-o',str(out/'qpack.dll')]
    p=subprocess.run(cmd,env=env,capture_output=True,text=True);(out/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    cookie=os.add_dll_directory(str(GCC.parent));lib=ctypes.CDLL(str(out/'qpack.dll'));pack=lib.road_qconv_pack;pack.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t];pack.restype=ctypes.c_int
    blob=bytearray();rows=[];layout={}
    for t in g['tensors'][1:]:
        if t['kind']!=1:continue
        i=t['id'];inp=g['tensors'][t['inputs'][0]];ic=inp['c4'];oc=t['c4'];k=t['k'];groups=(ic+7)//8;blocks=(oc+15)//16
        w=arrays[f'weight_{i}'];expanded=np.zeros((k,k,groups*8,blocks*16),np.int8);expanded[:,:,:ic,:oc]=w
        expected=expanded.reshape(k,k,groups,8,blocks,16).transpose(4,0,1,2,5,3).copy().ravel();actual=np.full(len(expected)+64,0x55,np.int8)
        assert pack(w.ctypes.data,ic,oc,k,actual.ctypes.data,len(expected))==0 and np.array_equal(actual[:len(expected)],expected) and np.all(actual[len(expected):]==0x55)
        assert pack(w.ctypes.data,ic,oc,k,actual.ctypes.data,len(expected)-1)==2
        blob.extend(bytes((-len(blob))%64));offset=len(blob);blob.extend(expected.tobytes());layout[i]=(offset,len(expected))
        rows.append(dict(node=i,offset=offset,bytes=len(expected),red_groups=k*k*groups,output_blocks=blocks,c_pack_bytes_exact=True,tail_guard=True,insufficient_capacity_rejected=True))
    assert len(rows)==60 and len(blob)<0x200000
    (out/'packed_weights.bin').write_bytes(blob)
    meta=np.zeros((len(q['channels']),8),'<i4')
    for i,c in enumerate(q['channels']):meta[i,:7]=[c[key] for key in ['split','lb','ln','lo','rb','rn','ro']]
    meta.tofile(out/'metadata.bin');assert len(meta.tobytes())<0x100000
    table_count=(q['float_base']-q['threshold_base'])//4;assert table_count<=2097152
    header=['#ifndef ROAD_QCONV_LAYOUT_H','#define ROAD_QCONV_LAYOUT_H',f'#define QCONV_PACKED_BYTES {len(blob)}U',f'#define QCONV_METADATA_BYTES {len(meta.tobytes())}U',f'#define QCONV_TABLE_COUNT {table_count}U','typedef struct {unsigned offset,bytes;} QConvLayout;','static const QConvLayout QCONV_LAYOUT[ROAD_TENSORS]={']
    for t in g['tensors']:
        offset,n=layout.get(t['id'],(0,0));header.append('{%dU,%dU},'%(offset,n))
    header+=['};','#endif'];(out/'road_qconv_layout.h').write_text('\n'.join(header)+'\n',encoding='ascii')
    quality=json.loads((ROOT/'final_holdout_complete.json').read_text())
    result=dict(status='ALL60_NATIVE_C_PACKING_BYTES_EXACT_TO_NUMPY_AND_GUARDS_PASS_EXPERIMENT_ONLY',quant_model_sha256=sha(source/'qmodel.bin'),packed_sha256=sha(out/'packed_weights.bin'),metadata_sha256=sha(out/'metadata.bin'),rows=rows,table_count=table_count,fresh_accuracy_gate_passed=quality['passed'],default_promotion_allowed=False,hardware_access=False,sd_written=False,command=cmd)
    (out/'complete.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ROAD_QCONV_ALL60_MODEL_PACKING_PASS',len(blob),'bytes; accuracy gate',quality['passed'],flush=True)
if __name__=='__main__':main()
