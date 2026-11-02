"""Isolated FP32 1x1/3x3 shared core, fixed references before synthesis/board work."""
from pathlib import Path
import json,shutil,subprocess,os
import numpy as np
from prepare_fp32_cpu_pack import BASE,NN,CURRENT,read,write,sha,HERE
ROOT=BASE/'road_conv13_hls_20261028_r1'
OLD=BASE/'road_conv_burst_hls_20261027'
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')

def main():
    ROOT.mkdir(exist_ok=False)
    source=(OLD/'road_conv3_hls.cpp').read_text()
    header=(OLD/'road_conv3_hls.h').read_text()
    for text,name in [(source,'road_conv3_hls.cpp'),(header,'road_conv3_hls.h')]:
        text=text.replace('int oc4,int stride)','int oc4,int stride,int kernel)')
        if name.endswith('.cpp'):
            text=text.replace('#pragma HLS INTERFACE s_axilite port=stride bundle=control','#pragma HLS INTERFACE s_axilite port=stride bundle=control\n#pragma HLS INTERFACE s_axilite port=kernel bundle=control')
            text=text.replace('ic4>128','ic4>(kernel==1?512:128)')
            text=text.replace('if(height<1','if((kernel!=1&&kernel!=3)||(kernel==1&&stride!=1)||height<1',1)
            text=text.replace('float patch[3][RC_PATCH*RC_MAX_IC];','float patch[3*RC_PATCH*RC_MAX_IC];')
            text=text.replace('const int red=9*ic4','const int red=kernel*kernel*ic4')
            text=text.replace(')+3;',')+kernel;').replace('2*y:y)-1','2*y:y)-(kernel/2)').replace('2*x0:x0)-1','2*x0:x0)-(kernel/2)')
            text=text.replace('ky<3','ky<kernel').replace('kx==3','kx==kernel')
            for a,b in [('patch[ky][offset+r]','patch[ky*RC_PATCH*RC_MAX_IC+offset+r]'),('patch[ky][r]','patch[ky*RC_PATCH*RC_MAX_IC+r]'),('patch[ky][col*ic4+ic]','patch[ky*RC_PATCH*RC_MAX_IC+col*ic4+ic]')]:text=text.replace(a,b)
            text=text.replace('max=4224','max=8192')
            assert 'patch[ky][' not in text and 'ky<3' not in text and ')+3;' not in text
        (ROOT/name).write_text(text,encoding='ascii')
    tb=(OLD/'tb_road_conv3.cpp').read_text()
    tb=tb.replace('int h,w,ic,oc,s;','int h,w,ic,oc,s,k;').replace('meta>>h>>w>>ic>>oc>>s;','meta>>h>>w>>ic>>oc>>s>>k;').replace('(9*ic+1)','(k*k*ic+1)')
    tb=tb.replace('h,w,ic,oc,s);','h,w,ic,oc,s,k);')
    for args in ['0,5,4,8,1','161,5,4,8,1','3,5,6,8,1','3,5,4,8,3','160,160,4,8,1']:
        tb=tb.replace(args+')',args+',3)')
    tb=tb.replace('std::cout<<"ROAD_CONV3_TESTBENCH_ALL_PASS','if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,4,8,1,2)!=1||output[0]!=guard)return 14;\n if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,512,8,1,3)!=1||output[0]!=guard)return 15;\n if(road_conv3_fp32(input.data(),weights.data(),output.data(),3,5,512,8,2,1)!=1||output[0]!=guard)return 16;\n std::cout<<"ROAD_CONV3_TESTBENCH_ALL_PASS')
    tb=tb.replace('invalid_guards=5','invalid_guards=8')
    (ROOT/'tb_road_conv3.cpp').write_text(tb,encoding='ascii')
    # Independent scalar reference for pointwise: same bias-first IC order.
    ref=(HERE/'road_conv3_reference.c').read_text().replace('(size_t)9*ic*oc','(size_t)ic*oc').replace('ky<3','ky<1').replace('kx<3','kx<1').replace('y*s+ky-1','y*s+ky').replace('x*s+kx-1','x*s+kx').replace('(ky*3+kx)','(ky+kx)')
    (ROOT/'point_reference.c').write_text(ref,encoding='ascii')
    env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env['PATH']
    p=subprocess.run([str(GCC),'-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror',str(ROOT/'point_reference.c'),'-o',str(ROOT/'point_reference.exe'),'-lm'],env=env,capture_output=True,text=True)
    (ROOT/'reference_build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    base=ROOT/'fixtures';base.mkdir();rows=[]
    for old in read(OLD/'fixtures.json'):
        r=dict(old);r['kernel']=3;folder=base/r['name'];shutil.copytree(OLD/'fixtures'/r['name'],folder)
        shape=(folder/'shape.txt').read_text().strip();(folder/'shape.txt').write_text(shape+' 3\n',encoding='ascii');rows.append(r)
    g=read(NN/'graph.json');ts=g['tensors'];weights=np.fromfile(CURRENT/'runtime/weights.f32','<f4')
    assert sha(CURRENT/'runtime/weights.f32')==sha(NN/'weights.f32')
    photo=read(BASE/'road_roi_spatial_verifier_20261028/native_detector_full/complete.json')['cases'][0]['name']
    trace=BASE/'road_roi_spatial_verifier_20261028/native_detector_full/cases'/photo/'host/trace'
    nodes=[t['id'] for t in ts[1:] if t['kind']==1 and t['k']==1 and ts[t['inputs'][0]]['c4']<=512 and t['c4']%8==0 and t['h']<=80 and t['w']<=80]
    assert len(nodes)==39
    def one(name,a,w,bias,post=None,node=None,rtl=False):
        h,ww,ic=a.shape;oc=len(bias);folder=base/name;folder.mkdir()
        a.astype('<f4').tofile(folder/'input.f32');w.astype('<f4').tofile(folder/'weights.f32');bias.astype('<f4').tofile(folder/'bias.f32')
        pack=np.empty((oc//8,ic+1,8),'<f4')
        for b in range(oc//8):pack[b,0]=bias[8*b:8*b+8];pack[b,1:]=w[:,8*b:8*b+8]
        pack.tofile(folder/'packed_p8.f32')
        (folder/'shape.txt').write_text(f'{h} {ww} {ic} {oc} 1 1\n',encoding='ascii')
        p=subprocess.run([str(ROOT/'point_reference.exe'),str(h),str(ww),str(ic),str(oc),'1',str(folder/'input.f32'),str(folder/'weights.f32'),str(folder/'bias.f32'),str(folder/'expected.f32'),str(folder/'expected_silu.f32')],capture_output=True,text=True)
        assert p.returncode==0,p.stderr
        if post is not None:assert (folder/'expected_silu.f32').read_bytes()==post,(name,'original postSiLU reference')
        rows.append(dict(name=name,h=h,w=ww,ic4=ic,oc4=oc,stride=1,kernel=1,rtl=rtl,origin=dict(node=node,photo=photo) if node else None,post_silu_original_tensor_bytes_exact=post is not None,files={p.name:sha(p) for p in folder.iterdir()}))
    for n in nodes:
        t=ts[n];inp=ts[t['inputs'][0]];a=np.fromfile(trace/f"{inp['id']:03d}.f32",'<f4').reshape(inp['h'],inp['w'],inp['c4'])
        w=weights[t['woff']:t['woff']+inp['c4']*t['c4']].reshape(inp['c4'],t['c4']);bias=weights[t['boff']:t['boff']+t['c4']]
        one(f'point_node{n:02d}',a,w,bias,(trace/f'{n:03d}.f32').read_bytes(),n,rtl=n==48)
    rng=np.random.default_rng(2026102839)
    for h,w,ic,oc,name in [(3,19,4,16,'point_cross_tile'),(1,1,512,256,'point_max_channels'),(2,17,256,8,'point_ic256'),(1,1,4,8,'point_single')]:
        one(name,rng.uniform(-1,1,(h,w,ic)).astype('f4'),rng.uniform(-.1,.1,(ic,oc)).astype('f4'),rng.uniform(-.2,.2,oc).astype('f4'),rtl=True)
    write(ROOT/'fixtures.json',rows)
    for mode in ['all','rtl']:(ROOT/f'cases_{mode}.txt').write_text('\n'.join(r['name'] for r in rows if mode=='all' or r['rtl'])+'\n',encoding='ascii')
    for stage in ['csim','synth','cosim','export']:
        text=(OLD/(stage+'.tcl')).read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace('-ipname road_conv3_burst_p8','-ipname road_conv13_p8')
        (ROOT/(stage+'.tcl')).write_text(text,encoding='ascii')
    shutil.copy2(OLD/'YOLOv5_LICENSE',ROOT/'YOLOv5_LICENSE')
    write(ROOT/'protocol.json',dict(status='SHARED_CORE_DESIGN_REFERENCES_FROZEN',target='xc7z020clg400-2',clock_ns=10,arithmetic='Unchanged FP32 bias-first separate multiply/add ky,kx,ic reduction; SiLU onARM',shapes='k3:IC<=128,stride1/2,IH/W<=160,OH/W<=80; k1:IC<=512,stride1,IH/W<=80; OC<=256 divisible8',storage='Flatten existing3*33*128 patch floats; k1 usesatmost16*512=8192, k3 atmost3*33*128=12672. Weight scratch remains9*128*8 floats.',pointwise_nodes=nodes,existing_selected_3x3_nodes=[2,5,10,13,16,21,35,38,63,67,75,79],acceptance='All Csim/RTL fixture outputs byteexact to independent scalar references; original postSiLU exact. Final physical whole86 tensors/outputs byteexact toABI15; full-frame >=5% median speed improvement and no video regression.',fixtures=len(rows),rtl_fixtures=sum(r['rtl'] for r in rows),weights_sha256=sha(CURRENT/'runtime/weights.f32'),sd_written=False,hardware_access=False))
    print('ROAD_CONV13_PREPARED',len(rows),len(nodes),flush=True)

if __name__=='__main__':main()
