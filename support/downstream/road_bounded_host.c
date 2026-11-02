#include <stdio.h>
#include <stdlib.h>
#include "road_bounded_luma.h"
int main(int argc,char **argv) {
    if(argc!=8)return 2;
    unsigned n=(unsigned)strtoul(argv[3],0,10),s=(unsigned)strtoul(argv[4],0,10),c=(unsigned)strtoul(argv[5],0,10),t=(unsigned)strtoul(argv[6],0,10);
    if(!n || n>1000000u || s>256u || c>64u || t==0u || t>255u)return 3;
    uint8_t *a=malloc(n*3u),*b=malloc(n*3u),*o=malloc(n*3u);if(!a||!b||!o)return 4;
    FILE *f=fopen(argv[1],"rb");if(!f || fread(a,3u,n,f)!=n)return 5;fclose(f);
    f=fopen(argv[2],"rb");if(!f || fread(b,3u,n,f)!=n)return 6;fclose(f);
    road_bounded_luma(a,b,o,n,s,c,t);
    f=fopen(argv[7],"wb");if(!f || fwrite(o,3u,n,f)!=n)return 7;fclose(f);free(a);free(b);free(o);return 0;
}
