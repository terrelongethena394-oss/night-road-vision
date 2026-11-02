#include "road_person_verifier.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int readall(const char *path,void *data,size_t n){FILE *f=fopen(path,"rb");int ok;if(!f)return 0;ok=fread(data,1,n,f)==n&&fgetc(f)==EOF;fclose(f);return ok;}
int main(int argc,char **argv){
 float weights[ROAD_PERSON_WEIGHTS];uint8_t patch[ROAD_PERSON_PATCH_BYTES];FILE *f,*g;unsigned n,i;
 if(argc==5&&!strcmp(argv[1],"crop")){
  uint8_t *src=malloc(800U*480U*3U);float b[6];RoadBox box;
  if(!src||!readall(argv[2],src,800U*480U*3U)||!readall(argv[3],b,24))return 2;
  box.x1=b[0];box.y1=b[1];box.x2=b[2];box.y2=b[3];box.score=b[4];box.cls=(int)b[5];box.order=0;
  if(road_person_crop(src,&box,patch))return 3;
  g=fopen(argv[4],"wb");if(!g||fwrite(patch,1,sizeof(patch),g)!=sizeof(patch))return 4;fclose(g);free(src);puts("PERSON_VERIFIER_CROP_PASS");return 0;
 }
 if(argc!=4||!readall(argv[1],weights,sizeof(weights)))return 5;
 f=fopen(argv[2],"rb");g=fopen(argv[3],"wb");if(!f||!g||fread(&n,4,1,f)!=1)return 6;
 for(i=0;i<n;i++){float p;if(fread(patch,1,sizeof(patch),f)!=sizeof(patch))return 7;p=road_person_probability(patch,weights);if(fwrite(&p,4,1,g)!=1)return 8;}
 if(fgetc(f)!=EOF)return 9;
 fclose(f);fclose(g);printf("PERSON_VERIFIER_NATIVE_DONE %u\n",n);return 0;
}
