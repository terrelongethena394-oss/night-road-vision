"""Exact4x8 NEON/SSE microkernel; separate matrix work from scalar activation."""
from pathlib import Path
import prepare_fp32_cpu_pack as common
BASE=common.BASE;ROOT=BASE/'road_fp32_microkernel_20261028_r3'
def patch(c):
 service='road_poll_service()' if 'road_pl_try(' in c else '((void)0)'
 code='''
static int cpu_mode=1;
void road_cpu_set_mode(int mode){cpu_mode=mode;}
static __attribute__((noinline)) void micro4x8(const float *restrict a,const float *restrict w,const float *restrict bias,float *restrict d,int ic4,int oc4){
 V4 a0=load4(bias),b0=load4(bias+4),a1=a0,a2=a0,a3=a0,b1=b0,b2=b0,b3=b0;int k;
 for(k=0;k<ic4;k++,w+=oc4){V4 v=load4(w),u=load4(w+4);float x=a[k];a0=mac4(a0,v,x);b0=mac4(b0,u,x);x=a[k+ic4];a1=mac4(a1,v,x);b1=mac4(b1,u,x);x=a[k+2*ic4];a2=mac4(a2,v,x);b2=mac4(b2,u,x);x=a[k+3*ic4];a3=mac4(a3,v,x);b3=mac4(b3,u,x);}
 store4(d,a0);store4(d+4,b0);store4(d+oc4,a1);store4(d+oc4+4,b1);store4(d+2*oc4,a2);store4(d+2*oc4+4,b2);store4(d+3*oc4,a3);store4(d+3*oc4+4,b3);
}
static __attribute__((noinline)) void micro4x4(const float *restrict a,const float *restrict w,const float *restrict bias,float *restrict d,int ic4,int oc4){
 V4 s=load4(bias),s1=s,s2=s,s3=s;int k;
 for(k=0;k<ic4;k++,w+=oc4){V4 v=load4(w);s=mac4(s,v,a[k]);s1=mac4(s1,v,a[k+ic4]);s2=mac4(s2,v,a[k+2*ic4]);s3=mac4(s3,v,a[k+3*ic4]);}
 store4(d,s);store4(d+oc4,s1);store4(d+2*oc4,s2);store4(d+3*oc4,s3);
}
static __attribute__((noinline)) void conv1_micro(const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *restrict a,const float *restrict weights,float *restrict b){
 int y,x,o,k;const int h=out->h,wid=out->w,ic4=in->c4,oc4=out->c4;const float *w=weights+op->wo,*bias=weights+op->bo;
 for(y=0;y<h;y++){
  for(x=0;x+3<wid;x+=4){const float *s=a+(y*wid+x)*ic4;float *d=b+(y*wid+x)*oc4;
   for(o=0;o+7<oc4;o+=8)micro4x8(s,w+o,bias+o,d+o,ic4,oc4);
   for(;o<oc4;o+=4)micro4x4(s,w+o,bias+o,d+o,ic4,oc4);
  }
  for(;x<wid;x++){const float *s=a+(y*wid+x)*ic4;float *d=b+(y*wid+x)*oc4;
   for(o=0;o<oc4;o+=4){V4 sum=load4(bias+o);const float *wp=w+o;for(k=0;k<ic4;k++,wp+=oc4)sum=mac4(sum,load4(wp),s[k]);store4(d+o,sum);}
  }
  if(op->act)for(x=0;x<wid;x++)for(o=0;o<out->c;o++){float *v=b+(y*wid+x)*oc4+o;*v=*v*sigmoid(*v);}
  SERVICE();
 }
}
'''.replace('SERVICE()',service)
 c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"',1).replace('static void conv(',code+'\nstatic void conv(',1)
 if 'if(op->kind==1){int offloaded=' in c:c=c.replace('if(op->kind==1){int offloaded=','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_micro(op,in,out,a,weights,b);\n    else if(op->kind==1){int offloaded=',1)
 else:c=c.replace('if(op->kind==1)conv(op,in,out,a,weights,b);','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_micro(op,in,out,a,weights,b);\n    else if(op->kind==1)conv(op,in,out,a,weights,b);',1)
 return c
def main():
 g=common.read(common.NN/'graph.json')
 for t in g['tensors'][1:]:
  if t['kind']==1 and t['k']==1:
   a=g['tensors'][t['inputs'][0]];assert a['offset']+a['elements']<=t['offset'] or t['offset']+t['elements']<=a['offset']
 common.ROOT=ROOT;common.patch=patch;common.main();p=common.read(ROOT/'protocol.json');p.update(arithmetic='Exact ordered FP32; original weights.4spatial x8output microkernel, noinline, no scalar activations inside hot matrix loop.',packed_bytes=0,packed_floats=0,packed_addr=None,restrict_justification='All42 pointwise layers have disjoint input/output arena ranges; weights separate.',reason='Cache-packed candidate was slower. Eight-spatial candidate has a632-byte kernel stack frame; this version isolates leaf matrix kernels from activation calls.')
 common.write(ROOT/'protocol.json',p);common.write(ROOT/'prepared.json',dict(status='MICROKERNEL_HOST_AND_ARM_SOURCE_READY',packed_bytes=0,source_sha256=common.sha(ROOT/'firmware/source/road_fp32.c')))
 import check_build_fp32_cpu_pack as run
 run.ROOT=ROOT;run.main()
if __name__=='__main__':main()
