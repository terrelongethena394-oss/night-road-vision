"""Prepare full-network offload wiring and verify host integration with an independent packed scalar model."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
ADAPTER=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027/arm_layout_adapter')
HERE=Path(__file__).resolve().parent
GCC=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def layout_header(selected):
    g=json.loads((NN/'graph.json').read_text());layout=json.loads((ADAPTER/'layout_p8.json').read_text());rows={v['node']:v for v in layout['layers']}
    lines=['#ifndef ROAD_PL_LAYOUT_H','#define ROAD_PL_LAYOUT_H',f'#define ROAD_PL_PACKED_BYTES {layout["bytes"]}U','typedef struct {unsigned offset,bytes,selected;} RoadPLLayout;','static const RoadPLLayout ROAD_PL_LAYOUT[ROAD_TENSORS]={']
    for t in g['tensors']:
        if t['id'] in rows:
            r=rows[t['id']];ip=g['tensors'][t['inputs'][0]];n=(9*ip['c4']+1)*t['c4']*4
            assert r['byte_offset']%64==0 and n==r['axi_word_count']*32
            assert (ip['offset']+ip['elements']<=t['offset']) or (t['offset']+t['elements']<=ip['offset'])
            assert ip['offset']%16==t['offset']%16==0 and ip['elements']%16==t['elements']%16==0
            lines.append('{%dU,%dU,%dU},'%(r['byte_offset'],n,int(t['id'] in selected)))
        else:lines.append('{0,0,0},')
    lines+=['};','#endif'];return '\n'.join(lines)+'\n'
def main():
    ROOT.mkdir(exist_ok=False);src=ROOT/'source';shutil.copytree(CAM/'source',src)
    for name in ['road_pl.h','road_pl.c','road_conv3_pack.c']:shutil.copy2(HERE/name,src/name)
    (src/'road_pl_layout.h').write_text(layout_header(set(range(86))),encoding='ascii')
    c=(src/'road_fp32.c').read_text();c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_pl.h"',1)
    old='if(op->kind==1)conv(op,in,out,a,weights,b);'
    new='if(op->kind==1){int offloaded=road_pl_try(i,op,in,out,a,weights,b,road_poll_service);if(offloaded<0)return offloaded;if(!offloaded)conv(op,in,out,a,weights,b);}'
    assert c.count(old)==1;c=c.replace(old,new);(src/'road_fp32.c').write_text(c,encoding='ascii')
    harness=(HERE/'road_fp32_host.c').read_text().replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_pl.h"')
    harness=harness.replace('road_preprocess400(raw,rgb);','if(road_pl_prepare(weights))return 20;\n  road_pl_begin();\n  road_preprocess400(raw,rgb);')
    harness=harness.replace('free(weights);free(arena);','printf("PACKED_SCALAR_OFFLOAD_CALLS=%u\\n",road_pl_host_calls);if(road_pl_host_calls!=17)return 21;\n  snprintf(path,sizeof(path),"%s/packed.bin",argv[3]);if(writefile(path,road_pl_host_packed(),4346176U))return 22;\n  free(weights);free(arena);')
    (src/'hybrid_host.c').write_text(harness,encoding='ascii')
    host=ROOT/'host';host.mkdir();env=os.environ.copy();env['PATH']=str(GCC.parent)+';'+env['PATH']
    cmd=[str(GCC),'-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-DROAD_PL_EMULATE','-I'+str(src),*[str(src/n) for n in ['road_fp32.c','road_pl.c','road_conv3_pack.c','hybrid_host.c']],'-lm','-o',str(host/'hybrid_host.exe')]
    p=subprocess.run(cmd,capture_output=True,text=True,env=env);(host/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    records=[];goldpack=(ADAPTER/'road_all3x3_p8.bin').read_bytes()
    for fixture in json.loads((NN/'export_complete.json').read_text())['fixtures']:
        name=fixture['name'];out=host/name;out.mkdir();trace=out/'trace';trace.mkdir()
        p=subprocess.run([str(host/'hybrid_host.exe'),str(NN/'weights.f32'),str(NN/'cases'/name/'input400.u32'),str(out),str(trace)],env=env,capture_output=True,text=True,check=True)
        assert 'PACKED_SCALAR_OFFLOAD_CALLS=17' in p.stdout
        assert (out/'packed.bin').read_bytes()==goldpack
        for f in (NN/'host_r2'/name/'trace').iterdir():assert (trace/f.name).read_bytes()==f.read_bytes(),(name,f.name)
        for n in ['decoded.f32','boxes320.f32','boxes400.f32','input320.rgb']:assert (out/n).read_bytes()==(NN/'host_r2'/name/n).read_bytes(),(name,n)
        records.append(dict(name=name,all86_tensors_decode_nms_bytes_exact=True,offloaded_emulated_layers=17));print('HYBRID_HOST_ALL86_AND_PACKING_EXACT',name,flush=True)
    (ROOT/'host_complete.json').write_text(json.dumps(dict(status='PACKED_SCALAR_EMULATION_ALL8_ALL86_EXACT_NOT_HARDWARE',cases=records,source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},command=cmd,hardware_access=False),indent=2),encoding='utf-8')
    print('ROAD_HYBRID_HOST_INTEGRATION_PASS_NOT_BOARD_TESTED',flush=True)
if __name__=='__main__':main()
