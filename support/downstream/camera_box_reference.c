/* Host arithmetic control of the current ARM snapshot's four-pixel average.
 * RGB/BGR channel-independent. This utility is not a board program. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
  const unsigned w=800,h=480;
  uint8_t *a=(uint8_t *)malloc(w*h*3),*b=(uint8_t *)malloc(w*h*3/4);
  FILE *f;if(argc!=3||!a||!b)return 2;
  f=fopen(argv[1],"rb");if(!f)return 3;
  if(fread(a,1,w*h*3,f)!=w*h*3)return 4;fclose(f);
  for(unsigned y=0;y<h/2;y++)for(unsigned x=0;x<w/2;x++)for(unsigned k=0;k<3;k++){
    unsigned at=(2*y*w+2*x)*3+k;
    b[(y*(w/2)+x)*3+k]=(a[at]+a[at+3]+a[at+w*3]+a[at+w*3+3]+2)/4;
  }
  f=fopen(argv[2],"wb");if(!f)return 5;
  if(fwrite(b,1,w*h*3/4,f)!=w*h*3/4)return 6;fclose(f);
  free(a);free(b);puts("CAMERA_BOX_HOST_DONE");return 0;
}
