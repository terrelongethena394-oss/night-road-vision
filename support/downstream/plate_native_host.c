#include <stdio.h>
#include "plate_native_kernel.h"
int main(int argc,char **argv){
 FILE *in,*out;uint8_t gray[3072],tokens[24];int32_t scores[1632];int count=0,n;
 if(argc!=3)return 2;
 in=fopen(argv[1],"rb");out=fopen(argv[2],"wb");if(!in||!out)return 3;
 while(fread(gray,1,3072,in)==3072){plate_infer(gray,scores);n=plate_decode(scores,tokens);(void)plate_valid(tokens,n);if(fwrite(scores,4,1632,out)!=1632)return 4;count++;}
 fclose(in);fclose(out);printf("PLATE_NATIVE_SCORES_WRITTEN %d\n",count);return 0;
}
