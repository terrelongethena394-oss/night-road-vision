"""Exact bucket directories reduce binary SiLU threshold searches, no model retuning."""
import os,shutil,subprocess,math,time
from pathlib import Path
import numpy as np
from road_integer_common import ROOT,read,write,sha
from verify_road_integer_host import GCC

def main():
    folder=ROOT/'m125';assert (folder/'host_complete.json').exists();out=folder/'fast_r1';out.mkdir(exist_ok=False)
    src=out/'source';shutil.copytree(folder/'source',src);qg=read(folder/'quant_graph.json');blob=(folder/'qmodel.bin').read_bytes()
    th=np.frombuffer(blob,'<i4',offset=qg['threshold_base'],count=(qg['float_base']-qg['threshold_base'])//4);records=[];checks=0
    for c in qg['channels']:
        r=th[c['ro']:c['ro']+c['rn']];n=len(r)
        if n:
            first=int(r[0]);span=int(r[-1])-first+1;shift=max(0,(span-1).bit_length()-4)
            while (1<<shift)*16<span:shift+=1
            dirs=np.searchsorted(r,[first+(i<<shift) for i in range(17)],side='left').tolist()
            vals=set([first-1,first,int(r[-1]),int(r[-1])+1])
            for v in r:vals.update([int(v)-1,int(v),int(v)+1])
            for a in vals:
                if a<first:count=0
                elif a>=r[-1]:count=n
                else:
                    bucket=(a-first)>>shift;lo,hi=dirs[bucket:bucket+2];count=lo+int(np.searchsorted(r[lo:hi],a,side='right'))
                assert count==int(np.searchsorted(r,a,side='right'));checks+=1
        else:first=shift=0;dirs=[0]*17
        assert max(dirs)<=254
        records.append(dict(first=first,shift=shift,dirs=dirs))
    header='/* Exact derived search directories, GPL-3.0. */\n#include <stdint.h>\ntypedef struct{int32_t first;uint8_t shift,dir[17];} QFast;\nstatic const QFast Q_FAST[]={\n'
    header+=',\n'.join('{'+str(r['first'])+','+str(r['shift'])+',{'+','.join(map(str,r['dirs']))+'}}' for r in records)+'\n};\n'
    (src/'road_q8_fast.h').write_text(header,encoding='ascii');p=src/'road_q8.c';code=p.read_text();code=code.replace('#include "road_q8_tables.h"','#include "road_q8_tables.h"\n#include "road_q8_fast.h"')
    old="""  return (int8_t)(acc<=ch->split?ch->lb+upper_count(table+ch->lo,ch->ln,-acc):ch->rb+upper_count(table+ch->ro,ch->rn,acc));"""
    new="""  const int32_t *r=table+ch->ro;const QFast *f=Q_FAST+(ch-Q_CHANNELS);int bucket,lo,hi;
  if(acc<=ch->split)return (int8_t)(ch->lb+upper_count(table+ch->lo,ch->ln,-acc));
  if(ch->rn==0||acc<f->first)return (int8_t)ch->rb;
  if(acc>=r[ch->rn-1])return (int8_t)(ch->rb+ch->rn);
  bucket=(acc-f->first)>>f->shift;lo=f->dir[bucket];hi=f->dir[bucket+1];
  return (int8_t)(ch->rb+lo+upper_count(r+lo,hi-lo,acc));"""
    assert code.count(old)==1;code=code.replace(old,new);p.write_text(code,encoding='ascii')
    env=os.environ.copy();env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','');commands=[]
    for tag,extra in [('simd',[]),('ap',['-DROAD_HOST_CONFIDENCE=.001f'])]:
        cmd=[str(GCC),'-O3','-std=c99','-msse2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror',*extra,'-I'+str(src),str(p),str(src/'road_fp32_host.c'),'-o',str(out/('road_'+tag+'.exe')),'-lm']
        r=subprocess.run(cmd,env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr;commands.append(cmd)
    import re,statistics
    from road_integer_common import FLOAT
    proof=[]
    for fixture in read(FLOAT/'export_complete.json')['fixtures']:
        name=fixture['name'];case=out/name;case.mkdir();trace=case/'trace';trace.mkdir()
        r=subprocess.run([str(out/'road_simd.exe'),str(folder/'qmodel.bin'),str(FLOAT/'cases'/name/'input400.u32'),str(case),str(trace)],capture_output=True,text=True,check=True)
        for file in (folder/'host'/name/'trace').iterdir():assert file.read_bytes()==(trace/file.name).read_bytes(),(name,file.name)
        for file in ['decoded.f32','boxes320.f32','boxes400.f32']:assert (case/file).read_bytes()==(folder/'host'/name/file).read_bytes()
        proof.append(dict(name=name,all86_layers_and_decoded_and_nms_bytes_exact=True,stdout=r.stdout.strip()));print('Q8_FAST_EXACT_PASS',name,flush=True)
    timings=[];case=out/read(FLOAT/'export_complete.json')['fixtures'][0]['name']
    configs={'fp32':(FLOAT/'host_r2/road_simd.exe',FLOAT/'weights.f32'),'q8plain':(folder/'host/road_simd.exe',folder/'qmodel.bin'),'q8fast':(out/'road_simd.exe',folder/'qmodel.bin')}
    for cycle in range(7):
        order=list(configs) if cycle%2==0 else list(configs)[::-1]
        for tag in order:
            exe,model=configs[tag];r=subprocess.run([str(exe),str(model),str(FLOAT/'cases'/case.name/'input400.u32'),str(case)],capture_output=True,text=True,check=True)
            timings.append(dict(cycle=cycle,tag=tag,cpu_seconds=float(re.search(r'cpu_seconds=([\d.]+)',r.stdout)[1])))
    med={tag:statistics.median(r['cpu_seconds'] for r in timings if r['tag']==tag and r['cycle']>0) for tag in configs}
    # Restore fast numerical output after the timing loop used the same folder.
    subprocess.run([str(out/'road_simd.exe'),str(folder/'qmodel.bin'),str(FLOAT/'cases'/case.name/'input400.u32'),str(case)],capture_output=True,text=True,check=True)
    write(out/'complete.json',dict(status='EXACT_DERIVED_BUCKET_SEARCH_ALL_BOUNDARIES_AND_ALL86_TENSORS_PASS',threshold_boundary_checks=checks,fixtures=proof,commands=commands,
       source_sha256={p.name:sha(p) for p in src.iterdir()},timings=timings,host_only_median_cpu_seconds=med,
       directory_storage_bytes_per_channel=24,total_directory_storage_bytes=24*len(records),no_accuracy_change=True,arm_timing_unknown=True,no_hardware=True))
    print('Q8_EXACT_SEARCH_HOST_ONLY_TIMINGS',med,flush=True)
if __name__=='__main__':main()
