"""Paired host CPU timing; NEVER extrapolate x86 results to Cortex-A9."""
import re,subprocess,statistics,time
from road_integer_common import ROOT,FLOAT,read,write,sha

def main():
    out=ROOT/'paired_host_benchmark';out.mkdir(exist_ok=False)
    configs={'fp32':(FLOAT/'host_r2/road_simd.exe',FLOAT/'weights.f32'),'q8':(ROOT/'m125/host/road_simd.exe',ROOT/'m125/qmodel.bin')}
    case=FLOAT/'cases'/read(FLOAT/'export_complete.json')['fixtures'][0]['name']/'input400.u32';records=[]
    for cycle in range(7):
        order=['fp32','q8'] if cycle%2==0 else ['q8','fp32']
        for tag in order:
            d=out/(tag+str(cycle));d.mkdir();exe,model=configs[tag];start=time.perf_counter()
            p=subprocess.run([str(exe),str(model),str(case),str(d)],capture_output=True,text=True,check=True)
            cpu=float(re.search(r'cpu_seconds=([\d.]+)',p.stdout)[1]);records.append(dict(cycle=cycle,tag=tag,warmup=cycle==0,cpu_seconds=cpu,wall_seconds=time.perf_counter()-start,stdout=p.stdout.strip()))
    med={tag:statistics.median(r['cpu_seconds'] for r in records if r['tag']==tag and not r['warmup']) for tag in configs}
    write(out/'complete.json',dict(status='MATCHED_X86_HOST_CPU_ONLY_BENCHMARK',records=records,median_cpu_seconds=med,ratio_fp32_over_q8=med['fp32']/med['q8'],
        warning='Host SSE2 and ARM NEON have different costs. No claim of board speedup or live-camera FPS. Training process may affect host load.',
        files={str(p):sha(p) for paths in configs.values() for p in paths},case_sha256=sha(case)))
    print('HOST_ONLY_PAIRED_TIMING',med,med['fp32']/med['q8'],flush=True)
if __name__=='__main__':main()
