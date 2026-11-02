#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int road_pack_conv3(const float *,const float *,int,int,int,float *,size_t);
static int load(const char *p,float *v,size_t n){FILE *f=fopen(p,"rb");int ok;if(!f)return 0;ok=fread(v,4,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 int ic,oc,pe;size_t nw,n;float *w,*b,*d,*copy;FILE *f;
 if(argc!=7)return 2;
 ic=atoi(argv[1]);oc=atoi(argv[2]);pe=atoi(argv[3]);if(ic<1||oc<1||ic>128||oc>256)return 3;
 nw=(size_t)9*ic*oc;n=nw+oc;w=malloc(nw*4);b=malloc(oc*4);d=malloc(n*4+128);copy=malloc(n*4+128);if(!w||!b||!d||!copy)return 4;
 if(!load(argv[4],w,nw)||!load(argv[5],b,oc))return 5;
 memset(d,0xA5,n*4+128);memcpy(copy,d,n*4+128);
 if(road_pack_conv3(w,b,ic,oc,pe,d,n-1)!=2||memcmp(copy,d,n*4+128))return 6;
 if(road_pack_conv3(w,b,ic,oc,3,d,n)!=1||memcmp(copy,d,n*4+128))return 7;
 if(road_pack_conv3(w,b,ic,oc,pe,d,n))return 8;
 if(memcmp((char *)d+n*4,(char *)copy+n*4,128))return 9;
 f=fopen(argv[6],"wb");if(!f)return 10;if(fwrite(d,4,n,f)!=n)return 11;fclose(f);
 free(w);free(b);free(d);free(copy);puts("CONV3_C_PACKER_DONE_GUARDS_AND_INVALID_CAPACITY_PASS");return 0;
}
