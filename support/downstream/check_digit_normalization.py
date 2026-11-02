"""Independent host-C/NumPy exhaustive constants and random input check."""
from pathlib import Path
import os,subprocess
import numpy as np
from recognition_upgrade_common import ROOT,BASE,SEED,normalize_np,write,sha
HERE=Path(__file__).resolve().parent
def main():
    out=ROOT/'normalization_proof';out.mkdir(exist_ok=True)
    (out/'digit_normalization.h').write_bytes((HERE/'digit_normalization.h').read_bytes())
    (out/'check.c').write_text('#include <stdio.h>\n#include "digit_normalization.h"\nint main(int argc,char **argv){FILE *a,*b;uint8_t x[784];if(argc!=3)return 2;a=fopen(argv[1],"rb");b=fopen(argv[2],"wb");if(!a||!b)return 3;while(fread(x,1,784,a)==784){digit_normalize(x);if(fwrite(x,1,784,b)!=784)return 4;}fclose(a);fclose(b);return 0;}\n',encoding='ascii')
    gcc=Path('E:/Xilinx/Vitis_HLS/2020.2/tps/mingw/6.2.0/win64.o/nt/bin/gcc.exe');env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
    r=subprocess.run([str(gcc),'-std=c99','-O2','-Wall','-Wextra','-Werror','-static',str(out/'check.c'),'-o',str(out/'check.exe')],capture_output=True,text=True,env=env);assert r.returncode==0,r.stderr
    rng=np.random.default_rng(SEED)
    x=np.concatenate([np.broadcast_to(np.arange(256,dtype=np.uint8)[:,None,None],(256,28,28)),rng.integers(0,256,(1000,28,28),dtype=np.uint8),rng.integers(100,132,(1000,28,28),dtype=np.uint8)])
    (out/'input.gray').write_bytes(x.tobytes())
    subprocess.run([str(out/'check.exe'),str(out/'input.gray'),str(out/'output.gray')],check=True)
    a=np.fromfile(out/'output.gray',np.uint8).reshape(-1,28,28);assert np.array_equal(a,normalize_np(x))
    write(out/'complete.json',dict(status='C_NUMPY_NORMALIZATION_EXACT',cases=len(x),bytes=int(x.size),header_sha256=sha(out/'digit_normalization.h'),contract_version=2))
    print('NORMALIZATION_EXACT',len(x),x.size)
if __name__=='__main__':main()
