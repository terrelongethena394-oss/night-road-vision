#include <stdio.h>
#include <stdlib.h>
#include "digit_arm_kernel.h"
int main(int argc,char **argv){
 FILE *in,*out;uint8_t gray[784];int64_t scores[11];int label,count=0;
 if(argc!=3)return 2;
 in=fopen(argv[1],"rb");out=fopen(argv[2],"wb");if(!in||!out)return 3;
 while(fread(gray,1,784,in)==784){label=digit_infer(gray,scores);(void)label;
  if(fwrite(scores,sizeof(int64_t),11,out)!=11)return 4;
  count++;
 }
 fclose(in);fclose(out);printf("NATIVE_CNN_LOGITS_WRITTEN %d\n",count);return 0;
}
