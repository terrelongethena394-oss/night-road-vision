/* Remove only the explicitly identified historical BOOT backup after PC backup.
 * No formatting, raw-sector writes, wildcard deletion or Flash operations. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ff.h"
#include "xil_cache.h"
#include "legacy_config.h"
#define MB ((volatile uint32_t *)0x03000000U)
#define NEW ((uint8_t *)0x12000000U)
#define OLD ((uint8_t *)0x14000000U)
#define LIST ((char *)0x16000000U)
#define LIMIT (32U*1024U*1024U)
static FATFS fs;
static uint32_t old_size,old_crc;
static uint32_t crc32(const uint8_t *p,uint32_t n){uint32_t c=0xffffffffU;while(n--){c^=*p++;for(unsigned j=0;j<8;j++)c=(c>>1)^(0xedb88320U&(0U-(c&1U)));}return ~c;}
static unsigned load(const char *name,uint8_t *dst,uint32_t *size){
 FIL f;FRESULT r=f_open(&f,name,FA_READ);if(r!=FR_OK)return r;
 FSIZE_t total=f_size(&f);if(total>LIMIT){(void)f_close(&f);return 1001;}
 uint32_t at=0;while(at<(uint32_t)total){UINT count=0,amount=((uint32_t)total-at>65536U)?65536U:(uint32_t)total-at;
  r=f_read(&f,dst+at,amount,&count);if(r!=FR_OK||count!=amount){(void)f_close(&f);return 1002;}at+=count;
 }
 r=f_close(&f);*size=(uint32_t)total;return r;
}
static unsigned check_new(void){uint32_t n=0;unsigned r=load("0:/BOOT.BIN",NEW,&n);if(r)return r;MB[7]=n;MB[8]=crc32(NEW,n);return n==EXPECTED_BOOT_BYTES&&MB[8]==EXPECTED_BOOT_CRC?0:1101;}
static unsigned list_root(void){
 DIR dir;FILINFO info;FRESULT r=f_opendir(&dir,"0:/");if(r)return r;unsigned at=0;
 for(;;){r=f_readdir(&dir,&info);if(r){(void)f_closedir(&dir);return r;}if(!info.fname[0])break;
  if(at+256U>=1048576U){(void)f_closedir(&dir);return 1201;}
  int n=snprintf(LIST+at,1048576U-at,"%s\t%c\t%lu\n",info.fname,(info.fattrib&AM_DIR)?'D':'F',(unsigned long)info.fsize);
  if(n<0||(unsigned)n>=1048576U-at){(void)f_closedir(&dir);return 1202;}at+=(unsigned)n;
 }
 MB[22]=at;return f_closedir(&dir);
}
static void fail(unsigned error){MB[5]=error;MB[2]=4;for(;;){}}
int main(void){
 Xil_DCacheDisable();Xil_ICacheDisable();for(unsigned i=0;i<64;i++)MB[i]=0;MB[0]=0x53444331U;MB[1]=1;MB[2]=2;
 unsigned r=f_mount(&fs,"0:",1);if(r)fail(r);r=check_new();if(r)fail(r);
 r=load("0:/B0000001.BIN",OLD,&old_size);if(r)fail(r);old_crc=crc32(OLD,old_size);MB[9]=old_size;MB[10]=old_crc;
 if(old_size<48U||((uint32_t *)OLD)[8]!=0xaa995566U||((uint32_t *)OLD)[9]!=0x584c4e58U)fail(1301);
 r=list_root();if(r)fail(r);MB[2]=1;
 for(;;){
  if(MB[3]!=1U)continue;MB[3]=0;MB[2]=2;
  if(MB[20]!=0x4241434bU||MB[25]!=old_size||MB[26]!=old_crc)fail(1401);
  uint32_t n=0;r=load("0:/B0000001.BIN",OLD,&n);if(r)fail(r);if(n!=old_size||crc32(OLD,n)!=old_crc)fail(1402);
  r=check_new();if(r)fail(r);
  r=f_unlink("0:/B0000001.BIN");if(r)fail(r);FILINFO info;r=f_stat("0:/B0000001.BIN",&info);if(r!=FR_NO_FILE)fail(1403);
  MB[24]=1;r=check_new();if(r)fail(r);r=list_root();if(r)fail(r);
  r=f_mount(0,"0:",0);if(r)fail(r);MB[21]=1;MB[5]=0;MB[2]=3;for(;;){}
 }
}
