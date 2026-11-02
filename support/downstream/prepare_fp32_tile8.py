"""Second candidate: reuse each original weight across8positions; no weight duplication."""
from pathlib import Path
import shutil,json
import prepare_fp32_cpu_pack as common
BASE=common.BASE;ROOT=BASE/'road_fp32_tile8_20261028_r2';HERE=Path(__file__).resolve().parent
def patch(c):
 service='road_poll_service()' if 'road_pl_try(' in c else '((void)0)'
 code='''
static int cpu_mode=1;
void road_cpu_set_mode(int mode){cpu_mode=mode;}
static __attribute__((noinline)) void conv1_tile8(const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b){
 const int ih=out->h,iw=out->w,ic4=in->c4,oc4=out->c4,oc=out->c;const float *w=weights+op->wo,*bias=weights+op->bo;int y,x,o,ic;
 for(y=0;y<ih;y++){
  for(x=0;x<iw;){int tile=x+7<iw?8:(x+3<iw?4:1);const float *sp=a+(y*iw+x)*ic4;float *dst=b+(y*iw+x)*oc4;
   for(o=0;o<oc4;o+=4){const float *wp=w+o;V4 s0=load4(bias+o);
    if(tile==8){V4 s1=s0,s2=s0,s3=s0,s4=s0,s5=s0,s6=s0,s7=s0;
     for(ic=0;ic<ic4;ic++,wp+=oc4){V4 v=load4(wp);s0=mac4(s0,v,sp[ic]);s1=mac4(s1,v,sp[ic+ic4]);s2=mac4(s2,v,sp[ic+2*ic4]);s3=mac4(s3,v,sp[ic+3*ic4]);s4=mac4(s4,v,sp[ic+4*ic4]);s5=mac4(s5,v,sp[ic+5*ic4]);s6=mac4(s6,v,sp[ic+6*ic4]);s7=mac4(s7,v,sp[ic+7*ic4]);}
     store4(dst+o,s0);store4(dst+oc4+o,s1);store4(dst+2*oc4+o,s2);store4(dst+3*oc4+o,s3);store4(dst+4*oc4+o,s4);store4(dst+5*oc4+o,s5);store4(dst+6*oc4+o,s6);store4(dst+7*oc4+o,s7);
    }else if(tile==4){V4 s1=s0,s2=s0,s3=s0;
     for(ic=0;ic<ic4;ic++,wp+=oc4){V4 v=load4(wp);s0=mac4(s0,v,sp[ic]);s1=mac4(s1,v,sp[ic+ic4]);s2=mac4(s2,v,sp[ic+2*ic4]);s3=mac4(s3,v,sp[ic+3*ic4]);}
     store4(dst+o,s0);store4(dst+oc4+o,s1);store4(dst+2*oc4+o,s2);store4(dst+3*oc4+o,s3);
    }else{for(ic=0;ic<ic4;ic++,wp+=oc4)s0=mac4(s0,load4(wp),sp[ic]);store4(dst+o,s0);}
   }
   if(op->act){int p;for(p=0;p<tile;p++)for(o=0;o<oc;o++){float *v=dst+p*oc4+o;*v=*v*sigmoid(*v);}}
   x+=tile;
  }
  SERVICE();
 }
}
'''.replace('SERVICE()',service)
 c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"',1).replace('static void conv(',code+'\nstatic void conv(',1)
 if 'if(op->kind==1){int offloaded=' in c:c=c.replace('if(op->kind==1){int offloaded=','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_tile8(op,in,out,a,weights,b);\n    else if(op->kind==1){int offloaded=',1)
 else:c=c.replace('if(op->kind==1)conv(op,in,out,a,weights,b);','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_tile8(op,in,out,a,weights,b);\n    else if(op->kind==1)conv(op,in,out,a,weights,b);',1)
 return c
def main():
 common.ROOT=ROOT;common.patch=patch;common.main();p=common.read(ROOT/'protocol.json');p.update(arithmetic='Exact orderedFP32, original weight layout,8-spatial-output reuse for CPU1x1, separate noinline kernel to bound register pressure.',packed_bytes=0,packed_floats=0,packed_addr=None,reason='First contiguous-weight candidate slower in preliminary physical timing; baseline unchanged. This candidate removes duplicate weights and doubles reuse across spatial outputs.')
 common.write(ROOT/'protocol.json',p);common.write(ROOT/'prepared.json',dict(status='TILE8_HOST_AND_ARM_SOURCE_READY',packed_bytes=0,source_sha256=common.sha(ROOT/'firmware/source/road_fp32.c')))
def build():
 import check_build_fp32_cpu_pack as run
 run.ROOT=ROOT;run.main()
if __name__=='__main__':main();build()
