"""Exact1x1 weight-block packing, same FP32 summation order and detector weights."""
from pathlib import Path
import json,shutil,subprocess,os,hashlib
BASE=Path('E:/FPGA_Enhance_Work');ROOT=BASE/'road_fp32_cpu_pack_20261028_r1';CURRENT=BASE/'road_detail_board_20261028_r1/firmware';NN=BASE/'road_arm_prototype_20261026';HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(c):
 assert c.count('static void conv(')==1
 code='''
#ifdef ROAD_CPU_HOST_PACK
static float cpu_packed[ROAD_CPU_PACK_FLOATS];
#else
static float *const cpu_packed=(float *)0x19000000U;
#endif
static int cpu_ready,cpu_mode=1;
void road_cpu_set_mode(int mode){cpu_mode=mode;}
static void cpu_prepare(const float *weights){
 int i,o,ic,lane;
 for(i=1;i<ROAD_TENSORS;i++){
  const RoadOp *op=ROAD_OPS+i-1;const RoadTensor *in=ROAD_T+op->in[0],*out=ROAD_T+i;
  if(op->kind!=1||op->k!=1||op->s!=1||op->p!=0)continue;
  for(o=0;o<out->c4;o+=4)for(ic=0;ic<in->c4;ic++)for(lane=0;lane<4;lane++)
   cpu_packed[ROAD_CPU_PACK_OFFSET[i]+(o/4)*in->c4*4+ic*4+lane]=weights[op->wo+ic*out->c4+o+lane];
 }
 cpu_ready=1;
}
static void conv1_packed(int node,const RoadOp *op,const RoadTensor *in,const RoadTensor *out,const float *a,const float *weights,float *b){
 int y,x,o,ic;const float *bias=weights+op->bo,*w=cpu_packed+ROAD_CPU_PACK_OFFSET[node];
 for(y=0;y<out->h;y++){
  for(x=0;x<out->w;){
   int tile=x+3<out->w?4:1;const float *src=a+(y*in->w+x)*in->c4;float *dst=b+(y*out->w+x)*out->c4;
   for(o=0;o<out->c4;o+=4){
    const float *wp=w+(o/4)*in->c4*4;V4 s=load4(bias+o);
    if(tile==4){V4 s1=s,s2=s,s3=s;
     for(ic=0;ic<in->c4;ic++,wp+=4){V4 v=load4(wp);s=mac4(s,v,src[ic]);s1=mac4(s1,v,src[ic+in->c4]);s2=mac4(s2,v,src[ic+2*in->c4]);s3=mac4(s3,v,src[ic+3*in->c4]);}
     store4(dst+o,s);store4(dst+out->c4+o,s1);store4(dst+2*out->c4+o,s2);store4(dst+3*out->c4+o,s3);
    }else{for(ic=0;ic<in->c4;ic++,wp+=4)s=mac4(s,load4(wp),src[ic]);store4(dst+o,s);}
   }
   if(op->act){int p;for(p=0;p<tile;p++)for(o=0;o<out->c;o++){float *v=dst+p*out->c4+o;*v=*v*sigmoid(*v);}}
   x+=tile;
  }
  ROAD_CPU_SERVICE();
 }
}
'''
 c=c.replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"',1)
 c=c.replace('static void conv(',code+'\nstatic void conv(',1)
 c=c.replace('int i;if(!weights||!arena)return -1;','int i;if(!weights||!arena)return -1;if(cpu_mode&&!cpu_ready)cpu_prepare(weights);',1)
 if 'if(op->kind==1){int offloaded=' in c:
  c=c.replace('if(op->kind==1){int offloaded=','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_packed(i,op,in,out,a,weights,b);\n    else if(op->kind==1){int offloaded=',1);service='road_poll_service()'
 else:
  assert 'if(op->kind==1)conv(op,in,out,a,weights,b);' in c;c=c.replace('if(op->kind==1)conv(op,in,out,a,weights,b);','if(op->kind==1&&op->k==1&&op->s==1&&op->p==0&&cpu_mode)conv1_packed(i,op,in,out,a,weights,b);\n    else if(op->kind==1)conv(op,in,out,a,weights,b);',1);service='((void)0)'
 return c.replace('ROAD_CPU_SERVICE()',service)
def main():
 ROOT.mkdir(exist_ok=False);g=read(NN/'graph.json');offsets=[0]*len(g['tensors']);n=0;layers=[]
 for t in g['tensors'][1:]:
  if t['kind']==1 and t['k']==1 and t['s']==1 and t['p']==0:
   offsets[t['id']]=n;n+=g['tensors'][t['inputs'][0]]['c4']*t['c4'];layers.append(t['id'])
 h='#ifndef ROAD_CPU_PACK_H\n#define ROAD_CPU_PACK_H\n#define ROAD_CPU_PACK_FLOATS %dU\nstatic const unsigned ROAD_CPU_PACK_OFFSET[ROAD_TENSORS]={%s};\nvoid road_cpu_set_mode(int);\n#endif\n'%(n,','.join(map(str,offsets)))
 write(ROOT/'protocol.json',dict(status='PACKING_DESIGN_FROZEN_BEFORE_BOARD',arithmetic='Exact unchanged orderedFP32 MACs, same bias/paddedchannels/activation; only CPU1x1 weight addressing changes.',layers=layers,packed_floats=n,packed_addr=0x19000000,profile_addr=0x17400000,profile_bytes=696,packed_bytes=n*4,baseline='SameELF with modeCSR128=0; candidateCSR128=1. No quantization, retraining, lookup activations, or fast-math.',acceptance='All86 native on16 full/ROI fixtures exact; physical outputs byteexact tobaseline; sameimage1warmup3timed; require median gain>=5% and preserve camera/pixel guards.',previous_elf_sha256=sha(CURRENT/'road_detail.elf'),sd_written=False))
 native=ROOT/'native_source';native.mkdir()
 for name in ['road_fp32.c','road_fp32.h','road_graph.h']:shutil.copy2(NN/'source_r2'/name,native/name)
 (native/'road_cpu_pack.h').write_text(h,encoding='ascii');(native/'road_fp32.c').write_text(patch((native/'road_fp32.c').read_text(encoding='utf-8')),encoding='ascii');shutil.copy2(HERE/'road_fp32_host.c',native/'road_fp32_host.c')
 app=ROOT/'firmware';shutil.copytree(CURRENT,app,ignore=shutil.ignore_patterns('physical_r1','static_readback','obj','*.log'));src=app/'source';(src/'road_cpu_pack.h').write_text(h,encoding='ascii');(src/'road_fp32.c').write_text(patch((src/'road_fp32.c').read_text(encoding='utf-8')),encoding='ascii')
 mainc=(src/'road_camera_main.c').read_text(encoding='utf-8').replace('#include "road_fp32.h"','#include "road_fp32.h"\n#include "road_cpu_pack.h"').replace('m[M_VERSION]=15;','m[M_VERSION]=16;m[128]=1U;m[129]=0x17400000U;').replace('ROAD_ROI_EXPERIMENT_READY V15','ROAD_CPU_PACK_READY V16')
 mainc=mainc.replace(' RoadEnhanceStats es;',' road_cpu_set_mode((int)m[128]);m[132]=m[128];\n RoadEnhanceStats es;',1)
 old='static void trace(int id,const float *data,uint32_t n,void *p){(void)id;(void)p;memcpy((void *)(RC_TRACE+trace_cursor),data,n*4U);trace_cursor+=n*4U;}'
 new='static XTime profile_previous;\nstatic void trace(int id,const float *data,uint32_t n,void *p){XTime t=now();(void)p;if(m[M_TRACE_ENABLE]==2U){if(id)((volatile uint64_t *)0x17400000U)[id]=t-profile_previous;profile_previous=t;return;}memcpy((void *)(RC_TRACE+trace_cursor),data,n*4U);trace_cursor+=n*4U;}'
 assert old in mainc;mainc=mainc.replace(old,new);mainc=mainc.replace(' Xil_DCacheFlushRange(RC_ROI_INPUT',' Xil_DCacheFlushRange(0x17400000U,696U);\n Xil_DCacheFlushRange(RC_ROI_INPUT',1);(src/'road_camera_main.c').write_text(mainc,encoding='ascii')
 write(ROOT/'prepared.json',dict(status='PACKED_CPU_HOST_AND_ARM_SOURCES_PREPARED',packed_bytes=n*4,layers=layers,source_sha256=sha(src/'road_fp32.c')));print('CPU_PACK_SOURCES_READY',n*4,len(layers),flush=True)
if __name__=='__main__':main()
