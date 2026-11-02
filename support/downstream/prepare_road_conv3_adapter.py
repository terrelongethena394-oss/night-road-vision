import os,shutil,subprocess
import numpy as np
from prepare_road_conv3_hls import ROOT,HERE,GCC,NN,read,write,sha

def main():
    out=ROOT/'arm_layout_adapter';out.mkdir(exist_ok=False)
    for name in ['road_conv3_pack.c','road_conv3_pack_host.c']:shutil.copy2(HERE/name,out/name)
    env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
    cmd=[str(GCC),'-O3','-std=c99','-Wall','-Wextra','-Werror',str(out/'road_conv3_pack.c'),str(out/'road_conv3_pack_host.c'),'-o',str(out/'pack.exe')]
    p=subprocess.run(cmd,env=env,capture_output=True,text=True);assert p.returncode==0,p.stderr
    checks=[]
    for fixture in read(ROOT/'fixtures.json'):
        f=ROOT/'fixtures'/fixture['name'];h,w,ic,oc,s=map(int,(f/'shape.txt').read_text().split())
        for pe in [4,8]:
            target=out/(fixture['name']+f'_p{pe}.f32');p=subprocess.run([str(out/'pack.exe'),str(ic),str(oc),str(pe),str(f/'weights.f32'),str(f/'bias.f32'),str(target)],capture_output=True,text=True,check=True)
            assert 'GUARDS_AND_INVALID_CAPACITY_PASS' in p.stdout and target.read_bytes()==(f/f'packed_p{pe}.f32').read_bytes()
            checks.append(dict(case=fixture['name'],pe=pe,bytes_exact=True))
    g=read(NN/'graph.json');weights=np.fromfile(NN/'weights.f32','<f4')
    for pe in [4,8]:
        records=[];chunks=[];cursor=0
        for t in g['tensors'][1:]:
            if t['kind']!=1 or t['k']!=3:continue
            p=g['tensors'][t['inputs'][0]];ic=p['c4'];oc=t['c4'];assert ic<=128 and oc%pe==0
            w=weights[t['woff']:t['woff']+9*ic*oc].reshape(9*ic,oc);b=weights[t['boff']:t['boff']+oc]
            packed=np.empty((oc//pe,9*ic+1,pe),'<f4')
            for block in range(oc//pe):packed[block,0]=b[block*pe:block*pe+pe];packed[block,1:]=w[:,block*pe:block*pe+pe]
            pad=(-cursor)%16
            if pad:chunks.append(np.zeros(pad,'<f4'));cursor+=pad
            records.append(dict(node=t['id'],name=t['name'],byte_offset=cursor*4,axi_word_offset=cursor//pe,axi_word_count=packed.size//pe,h=p['h'],w=p['w'],ic4=ic,oc4=oc,stride=t['s'],packed_sha256=__import__('hashlib').sha256(packed.tobytes()).hexdigest()))
            chunks.append(packed.ravel());cursor+=packed.size
        a=np.concatenate(chunks).astype('<f4');a.tofile(out/f'road_all3x3_p{pe}.bin')
        write(out/f'layout_p{pe}.json',dict(status='OFFLINE_REPACKED_BIAS_AND_3X3_WEIGHTS_ONLY',pe=pe,words=cursor//pe,bytes=cursor*4,layers=records,source_weights_sha256=sha(NN/'weights.f32'),blob_sha256=sha(out/f'road_all3x3_p{pe}.bin'),
             note='Relative64B-aligned offsets only. No DDR address assigned and no hardware calls. CPU still performs SiLU and all unsupported operators. Input/output remain NHWC4 float32 with same byte layout.'))
    write(out/'complete.json',dict(status='HOST_ARM_COMPATIBLE_LAYOUT_ADAPTER_EXACT_ON_ALL22_CASES',checks=checks,compiler_command=cmd,hardware_access=False,sd_write=False))
    print('ROAD_CONV3_LAYOUT_ADAPTER_AND_WEIGHT_BLOBS_READY',len(checks),flush=True)
if __name__=='__main__':main()
