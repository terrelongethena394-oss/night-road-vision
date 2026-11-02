"""Sixteen output lanes; compact orthogonal RTL coverage frozen before results."""
import re,shutil,subprocess
import numpy as np
from prepare_fp32_cpu_pack import BASE,read,write,sha
from prepare_road_conv13 import ROOT as OLD
ROOT=BASE/'road_conv13_p16_hls_20261028_r1'
RUNTIME=BASE/'road_conv13_p16_runtime_20261028_r1'

def main():
    ROOT.mkdir(exist_ok=False)
    h=(OLD/'road_conv3_hls.h').read_text().replace('RC_PE!=4 && RC_PE!=8','RC_PE!=4 && RC_PE!=8 && RC_PE!=16').replace('RC_PE_must_be_4_or_8','RC_PE_must_be_4_or_8_or_16')
    (ROOT/'road_conv3_hls.h').write_text(h,encoding='ascii')
    c=(OLD/'road_conv3_hls.cpp').read_text().replace('#if RC_PE==8','#if RC_PE>=8')
    start=c.index('#if RC_PE>=8',c.index('MAC_INTERLEAVED:'));end=c.index('#endif',start)
    c=c[:end]+'#if RC_PE==16\n'+''.join(f'     acc[p][{o}]=fp_add<{o}>(acc[p][{o}],fp_mul<{o}>(a,weights[r][{o}]));\n' for o in range(8,16))+'#endif\n'+c[end:]
    # The new branch is specifically compiled as16; no8-lane IP is rebuilt.
    c=c.replace('depth=36896','depth=18448').replace('depth=204800','depth=102400')
    (ROOT/'road_conv3_hls.cpp').write_text(c,encoding='ascii')
    tb=(OLD/'tb_road_conv3.cpp').read_text()
    def guard(m):
        values=m[1].split(',');values[3]='16';return 'output.data(),'+','.join(values)+')'
    tb=re.sub(r'output\.data\(\),([0-9,]+)\)',guard,tb)
    (ROOT/'tb_road_conv3.cpp').write_text(tb,encoding='ascii')
    froot=ROOT/'fixtures';froot.mkdir();rows=[]
    for old in read(OLD/'fixtures.json'):
        r=dict(old);d=froot/r['name'];d.mkdir();src=OLD/'fixtures'/r['name'];h,w,ic,oc,s,k=map(int,(src/'shape.txt').read_text().split())
        a=np.fromfile(src/'input.f32','<f4');weights=np.fromfile(src/'weights.f32','<f4').reshape(k*k*ic,oc);bias=np.fromfile(src/'bias.f32','<f4');expected=np.fromfile(src/'expected.f32','<f4').reshape((h+s-1)//s,(w+s-1)//s,oc)
        if oc==8:weights=np.tile(weights,(1,2));bias=np.tile(bias,2);expected=np.tile(expected,(1,1,2));oc=16
        assert oc%16==0
        a.tofile(d/'input.f32');weights.tofile(d/'weights.f32');bias.tofile(d/'bias.f32');expected.tofile(d/'expected.f32')
        pack=np.empty((oc//16,k*k*ic+1,16),'<f4')
        for b in range(oc//16):pack[b,0]=bias[16*b:16*b+16];pack[b,1:]=weights[:,16*b:16*b+16]
        pack.tofile(d/'packed_p16.f32');(d/'shape.txt').write_text(f'{h} {w} {ic} {oc} {s} {k}\n',encoding='ascii')
        r.update(oc4=oc,rtl=r['name'] in ['cross_tile','odd_stride2','max_input_channels','max_output_channels','point_max_channels'])
        rows.append(r)
    rng=np.random.default_rng(2026102816)
    # Full16-position IC512 patch crosses previous4224-float bank extent;
    # maxOC256 is independently covered inpoint_max_channels.
    for name,real in [('point_wide_ic512',False),('point_real_crop',True)]:
        d=froot/name;d.mkdir();ic=512;oc=16;h=1;w=10 if real else 17
        if real:
            p=OLD/'fixtures/point_node48';a=np.fromfile(p/'input.f32','<f4').reshape(10,10,512)[:1].copy();weights=np.fromfile(p/'weights.f32','<f4').reshape(512,256)[:,:16].copy();bias=np.fromfile(p/'bias.f32','<f4')[:16].copy();expected=np.fromfile(p/'expected.f32','<f4').reshape(10,10,256)[:1,:,:16].copy()
        else:
            a=rng.uniform(-1,1,(h,w,ic)).astype('f4');weights=rng.uniform(-.1,.1,(ic,oc)).astype('f4');bias=rng.uniform(-.2,.2,oc).astype('f4')
        a.tofile(d/'input.f32');weights.tofile(d/'weights.f32');bias.tofile(d/'bias.f32')
        p=subprocess.run([str(OLD/'point_reference.exe'),str(h),str(w),str(ic),str(oc),'1',str(d/'input.f32'),str(d/'weights.f32'),str(d/'bias.f32'),str(d/'expected.f32')],capture_output=True,text=True);assert p.returncode==0,p.stderr
        if real:assert expected.tobytes()==(d/'expected.f32').read_bytes()
        pack=np.empty((1,ic+1,16),'<f4');pack[0,0]=bias;pack[0,1:]=weights;pack.tofile(d/'packed_p16.f32');(d/'shape.txt').write_text(f'{h} {w} {ic} {oc} 1 1\n',encoding='ascii')
        rows.append(dict(name=name,h=h,w=w,ic4=ic,oc4=oc,stride=1,kernel=1,rtl=True,origin='Original realpoint48 firstrow/first16channels' if real else 'seeded independent scalar reference'))
    for r in rows:r['files']={p.name:sha(p) for p in (froot/r['name']).iterdir() if p.is_file()}
    write(ROOT/'fixtures.json',rows)
    for mode in ['all','rtl']:(ROOT/f'cases_{mode}.txt').write_text('\n'.join(r['name'] for r in rows if mode=='all' or r['rtl'])+'\n',encoding='ascii')
    for stage in ['csim','synth','cosim','export']:
        t=(OLD/(stage+'.tcl')).read_text().replace(OLD.as_posix(),ROOT.as_posix()).replace('-DRC_PE=8','-DRC_PE=16').replace('COMPLETE_P8','COMPLETE_P16').replace('road_conv13_p8','road_conv13_p16')
        (ROOT/(stage+'.tcl')).write_text(t,encoding='ascii')
    shutil.copy2(OLD/'YOLOv5_LICENSE',ROOT/'YOLOv5_LICENSE')
    p=read(OLD/'protocol.json');p.update(status='P16_DESIGN_FROZEN_BEFORE_SIMULATION',pe=16,fixtures=len(rows),rtl_fixtures=sum(r['rtl'] for r in rows),rtl_coverage='Orthogonal dimensions/stride/tile/channel bounds:39real full layers inCsim; real512-channel crop inRTL, wide512-channel patch, independent512->256 maxOC case; complete original86tensor physical validation required.',parent_sources={n:sha(OLD/n) for n in ['road_conv3_hls.cpp','road_conv3_hls.h']},resource_gate='Must fit7020 and routed100MHz timing before deployment; no guaranteed speed claim')
    write(ROOT/'protocol.json',p)
    print('CONV13_P16_PREPARED',len(rows),sum(r['rtl'] for r in rows),flush=True)
    import prepare_road_conv13_runtime as runtime
    runtime.ROOT=RUNTIME;runtime.HLS=ROOT;runtime.PE=16;runtime.VERSION=18;runtime.main()

if __name__=='__main__':main()
