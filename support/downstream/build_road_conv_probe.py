"""Offline only: compile the original optimized CPU baseline and new PL probe."""
from pathlib import Path
import hashlib,json,os,re,shutil,struct,subprocess
HERE=Path(__file__).resolve().parent
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
HLS=Path('E:/FPGA_Enhance_Work/road_conv_hls_20261027')
ORIGINAL=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026/source_r2')
BSP=Path('E:/FPGA_Enhance_Work/multinex_static_20261025/vitis_ws/static_platform/export/static_platform/sw/static_platform/standalone_domain')
ARM=Path('E:/Xilinx/Vitis/2020.2/gnu/aarch32/nt/gcc-arm-none-eabi/bin')
MINGW=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def main():
    out=ROOT/'arm_probe';out.mkdir(exist_ok=False);src=out/'source';src.mkdir()
    commands=[]
    def run(cmd,env=None):
        commands.append([str(x) for x in cmd]);p=subprocess.run(commands[-1],capture_output=True,text=True,env=env)
        with (out/'build.log').open('a',encoding='utf-8') as f:f.write(p.stdout+p.stderr)
        assert p.returncode==0,p.stdout+p.stderr
        return p.stdout
    assert sha(ORIGINAL/'road_fp32.c')=='c8fd60cda9148f779b1ea6c89c1264e5e0c9f3966c0c84d6d04ef2fd632de47a'
    for name in ['road_fp32.h','road_graph.h']:shutil.copy2(ORIGINAL/name,src/name)
    text=(ORIGINAL/'road_fp32.c').read_text()
    text+='''\n/* Probe wrapper: unchanged optimized conv, activation excluded on both sides. */
void road_layer_cpu(const float *input,const float *weights,float *output,
 int h,int w,int ic,int oc,int stride){
 RoadOp op={0};RoadTensor in={0},out={0};
 in.h=h;in.w=w;in.c=ic;in.c4=ic;
 out.h=(h+stride-1)/stride;out.w=(w+stride-1)/stride;out.c=oc;out.c4=oc;
 op.k=3;op.s=stride;op.p=1;op.wo=0;op.bo=9*ic*oc;op.act=0;
 conv(&op,&in,&out,input,weights,output);
}
'''
    (src/'road_fp32.c').write_text(text,encoding='ascii')
    shutil.copy2(HERE/'road_conv_probe.c',src/'road_conv_probe.c')
    driver=HLS/'p8/conv_project/solution_100mhz/impl/ip/drivers/road_conv3_fp32_v1_0/src/xroad_conv3_fp32_hw.h'
    shutil.copy2(driver,src/driver.name)
    # CLI invokes exactly the CPU wrapper used by the ARM application.
    (src/'host_layer.c').write_text('''#include <stdio.h>
#include <stdlib.h>
void road_layer_cpu(const float *,const float *,float *,int,int,int,int,int);
static void read_f(const char *p,float *a,size_t n){FILE *f=fopen(p,"rb");if(!f||fread(a,4,n,f)!=n)exit(2);fclose(f);}
int main(int argc,char **argv){int h,w,ic,oc,s;size_t ni,nw,no;float *a,*b,*wgt;FILE *f;
 if(argc!=10)return 1;h=atoi(argv[1]);w=atoi(argv[2]);ic=atoi(argv[3]);oc=atoi(argv[4]);s=atoi(argv[5]);
 ni=(size_t)h*w*ic;nw=(size_t)9*ic*oc;no=(size_t)((h+s-1)/s)*((w+s-1)/s)*oc;
 a=malloc(ni*4);wgt=malloc((nw+oc)*4);b=malloc(no*4);if(!a||!wgt||!b)return 3;
 read_f(argv[6],a,ni);read_f(argv[7],wgt,nw);read_f(argv[8],wgt+nw,oc);
 road_layer_cpu(a,wgt,b,h,w,ic,oc,s);f=fopen(argv[9],"wb");if(!f||fwrite(b,4,no,f)!=no)return 4;fclose(f);free(a);free(b);free(wgt);return 0;}
''',encoding='ascii')
    env=os.environ.copy();env['PATH']=str(MINGW)+';'+env['PATH']
    host=out/'host_layer.exe'
    run([MINGW/'gcc.exe','-O3','-std=c99','-msse2','-fno-fast-math','-ffp-contract=off','-I'+str(src),src/'road_fp32.c',src/'host_layer.c','-lm','-o',host],env)
    tests=[]
    for case in json.loads((HLS/'fixtures.json').read_text()):
        base=HLS/'fixtures'/case['name'];output=out/(case['name']+'.f32')
        for name,digest in case['files'].items():assert sha(base/name)==digest
        run([host,*[str(case[k]) for k in ['h','w','ic4','oc4','stride']],base/'input.f32',base/'weights.f32',base/'bias.f32',output],env)
        assert output.read_bytes()==(base/'expected.f32').read_bytes(),case['name']
        tests.append(dict(name=case['name'],bytes_exact=True,output_sha256=sha(output)))
    old=Path('E:/FPGA_Enhance_Work/camera_plate_guarded_20261026')
    shutil.copy2(old/'Xilinx.spec',out/'Xilinx.spec')
    (src/'lscript.ld').write_text((old/'app_src/lscript.ld').read_text().replace(': 0x2000;',': 0x10000;'),encoding='ascii')
    flags=['-mcpu=cortex-a9','-mfpu=neon-vfpv3','-mfloat-abi=hard','-O3','-std=c99','-ffp-contract=off','-fno-fast-math','-fno-common','-Wall','-Wextra','-Werror','-g','-fstack-usage','-I'+str(src),'-I'+str(BSP/'bspinclude/include')]
    objects=[]
    for name in ['road_fp32.c','road_conv_probe.c']:
        obj=out/(name+'.o');run([ARM/'arm-none-eabi-gcc.exe',*flags,'-c',src/name,'-o',obj]);objects.append(obj)
    elf=out/'road_conv_probe.elf'
    run([ARM/'arm-none-eabi-gcc.exe',*flags[:3],'-Wl,-build-id=none','-specs='+str(out/'Xilinx.spec'),'-Wl,-T,'+str(src/'lscript.ld'),'-Wl,-Map,'+str(out/'road_conv_probe.map'),'-L'+str(BSP/'bsplib/lib'),'-o',elf,*objects,'-Wl,--start-group','-lxil','-lgcc','-lc','-lm','-Wl,--end-group'])
    raw=elf.read_bytes();assert raw[:7]==b'\x7fELF\x01\x01\x01' and struct.unpack_from('<H',raw,18)[0]==40
    phoff=struct.unpack_from('<I',raw,28)[0];ent,n=struct.unpack_from('<HH',raw,42);loads=[]
    for i in range(n):
        kind,off,va,pa,sz,ms,fl,al=struct.unpack_from('<8I',raw,phoff+i*ent)
        if kind==1 and ms:
            assert 0x100000<=pa<pa+ms<=0x1000000
            loads.append(dict(start=pa,end=pa+ms))
    regions=[('input',0x10000000,160*160*128*4),('packed',0x18000000,256*(9*128+1)*4),('pl_output',0x19000000,80*80*256*4+64),('cpu_output',0x1A000000,80*80*256*4),('raw_weight',0x1B000000,256*(9*128+1)*4),('mailbox',0x1F000000,4096)]
    params=(BSP/'bspinclude/include/xparameters.h').read_text();ddr_high=int(re.search(r'#define XPAR_PS7_DDR_0_S_AXI_HIGHADDR\s+(0x\w+)',params)[1],16)
    for i,(name,a,n) in enumerate(regions):
        assert a+n<=ddr_high+1
        for _,b,m in regions[:i]:assert a+n<=b or a>=b+m
        for load in loads:assert a+n<=load['start'] or a>=load['end']
    dis=run([ARM/'arm-none-eabi-objdump.exe','-d',elf]);(out/'disassembly.txt').write_text(dis)
    neon=len(re.findall(r'\bvmla\.f32\s+q\d+',dis));assert neon
    write(out/'compile_complete.json',dict(status='OFFLINE_COMPILED_NOT_BOARD_EXECUTED',elf=str(elf),elf_sha256=sha(elf),source_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()},original_cpu_kernel_sha256=sha(ORIGINAL/'road_fp32.c'),host_reference_tests=tests,neon_vmla_sites=neon,elf_loads=loads,ddr_high=ddr_high,regions=[dict(name=n,address=a,bytes=b) for n,a,b in regions],commands=commands,hardware_access=False,sd_written=False))
    print('ROAD_CONV_PROBE_OFFLINE_COMPILE_PASS',len(tests),'fixtures; NEON sites',neon,flush=True)
if __name__=='__main__':main()
