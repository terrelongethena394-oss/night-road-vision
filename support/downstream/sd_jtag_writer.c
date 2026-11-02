/* JTAG-controlled FatFs file update. No formatting or flash operations. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ff.h"
#include "xil_cache.h"

#define MB ((volatile uint32_t *)0x03000000u)
#define UPLOAD ((uint8_t *)0x10000000u)
#define READBACK ((uint8_t *)0x12000000u)
#define OLD ((uint8_t *)0x14000000u)
#define LIMIT (16u*1024u*1024u)
#define CHUNK 65536u
static FATFS fs;
static uint32_t old_size, old_crc, new_size, new_crc;
static int old_present, backup_read, staged, verified, committed;
static char backup_name[32];

static uint32_t crc32(const uint8_t *p, uint32_t n) {
    uint32_t c=0xffffffffu;
    while(n--) { c^=*p++; for(unsigned j=0;j<8;j++) c=(c>>1)^(0xedb88320u & (0u-(c&1u))); }
    return ~c;
}

static unsigned read_file(const char *name, uint8_t *buffer, uint32_t *size) {
    FIL f; FRESULT r=f_open(&f,name,FA_READ); if(r!=FR_OK) return r;
    FSIZE_t n=f_size(&f); if(n>LIMIT) { (void)f_close(&f); return 1001; }
    uint32_t at=0;
    while(at<(uint32_t)n) {
        UINT count=0, amount=((uint32_t)n-at>CHUNK)?CHUNK:(uint32_t)n-at;
        r=f_read(&f,buffer+at,amount,&count);
        if(r!=FR_OK || count!=amount) { (void)f_close(&f); return r!=FR_OK?(unsigned)r:1002u; }
        at+=count;
    }
    r=f_close(&f); if(r!=FR_OK) return r;
    *size=(uint32_t)n; return 0;
}

static unsigned probe(void) {
    FILINFO info; FRESULT r=f_stat("0:/BOOT.BIN",&info);
    if(r!=FR_OK && r!=FR_NO_FILE) return r;
    old_present=(r==FR_OK); old_size=old_present?(uint32_t)info.fsize:0;
    if(old_size>LIMIT || (old_present && (info.fattrib&AM_DIR))) return 1003;
    MB[9]=(uint32_t)old_present;MB[10]=old_size;MB[11]=fs.fs_type;
    MB[12]=fs.volbase;MB[13]=fs.csize;MB[15]=fs.n_fatent-2;
    r=f_stat("0:/PLTNEW.BIN",&info);
    if(r!=FR_NO_FILE) return r==FR_OK?1004u:(unsigned)r;
    for(unsigned i=1;i<=9999999u;i++) {
        (void)snprintf(backup_name,sizeof(backup_name),"0:/B%07u.BIN",i);
        r=f_stat(backup_name,&info);
        if(r==FR_NO_FILE) { MB[19]=i;return 0; }
        if(r!=FR_OK) return r;
    }
    return 1005;
}

static unsigned dispatch(unsigned cmd) {
    unsigned r; uint32_t n=0;
    MB[6]=cmd;
    if(cmd==1) return probe();
    if(cmd==2) {
        if(staged || committed) return 1100;
        r=probe();if(r) return r;
        if(old_present) { r=read_file("0:/BOOT.BIN",OLD,&n);if(r) return r; if(n!=old_size) return 1101; }
        old_crc=crc32(OLD,old_size);backup_read=1;MB[7]=old_size;MB[8]=old_crc;return 0;
    }
    if(cmd==3) {
        if(!backup_read || staged || committed || MB[20]!=0x4241434bu) return 1200;
        new_size=MB[16];new_crc=MB[17];
        if(!new_size || new_size>LIMIT || crc32(UPLOAD,new_size)!=new_crc) return 1201;
        DWORD free_clusters; FATFS *volume=0;
        FRESULT fr=f_getfree("0:",&free_clusters,&volume);
        if(fr!=FR_OK) return fr;
        MB[14]=free_clusters;
        if((uint64_t)free_clusters*volume->csize*512u < (uint64_t)new_size+65536u) return 1202;
        FIL f;fr=f_open(&f,"0:/PLTNEW.BIN",FA_WRITE|FA_CREATE_NEW);if(fr!=FR_OK) return fr;
        for(uint32_t at=0;at<new_size;) {
            UINT count=0,amount=(new_size-at>CHUNK)?CHUNK:new_size-at;
            fr=f_write(&f,UPLOAD+at,amount,&count);
            if(fr!=FR_OK || count!=amount) { (void)f_close(&f);return fr!=FR_OK?(unsigned)fr:1203u; }
            at+=count;
        }
        fr=f_sync(&f);FRESULT closed=f_close(&f);
        if(fr!=FR_OK || closed!=FR_OK) return fr!=FR_OK?(unsigned)fr:(unsigned)closed;
        staged=1;return 0;
    }
    if(cmd==4) {
        if(!staged || committed) return 1300;
        r=read_file("0:/PLTNEW.BIN",READBACK,&n);if(r) return r;
        MB[7]=n;MB[8]=crc32(READBACK,n);
        if(n!=new_size || MB[8]!=new_crc || memcmp(READBACK,UPLOAD,n)!=0) return 1301;
        verified=1;return 0;
    }
    if(cmd==5) {
        if(!verified || committed || MB[20]!=0x434f4d54u) return 1400;
        FILINFO info;FRESULT fr=f_stat("0:/BOOT.BIN",&info);
        if(old_present) {
            if(fr!=FR_OK) return fr;
            r=read_file("0:/BOOT.BIN",READBACK,&n);if(r) return r;
            if(n!=old_size || crc32(READBACK,n)!=old_crc || memcmp(READBACK,OLD,n)!=0) return 1401;
        } else if(fr!=FR_NO_FILE) return 1402;
        fr=f_stat(backup_name,&info);if(fr!=FR_NO_FILE) return 1403;
        if(old_present) { fr=f_rename("0:/BOOT.BIN",backup_name);if(fr!=FR_OK) return fr; }
        fr=f_rename("0:/PLTNEW.BIN","0:/BOOT.BIN");
        if(fr!=FR_OK) {
            if(old_present && f_rename(backup_name,"0:/BOOT.BIN")!=FR_OK) return 1499;
            return fr;
        }
        committed=1;return 0;
    }
    if(cmd==6) {
        if(!committed) return 1500;
        r=read_file("0:/BOOT.BIN",READBACK,&n);if(r) return r;
        MB[7]=n;MB[8]=crc32(READBACK,n);
        if(n!=new_size || MB[8]!=new_crc || memcmp(READBACK,UPLOAD,n)!=0) return 1501;
        return 0;
    }
    if(cmd==7) {
        if(!committed) return 1600;
        if(old_present) {
            r=read_file(backup_name,OLD,&n);if(r) return r;
            if(n!=old_size || crc32(OLD,n)!=old_crc) return 1601;
        }
        MB[7]=old_size;MB[8]=old_crc;return 0;
    }
    if(cmd==8) { FRESULT fr=f_mount(0,"0:",0);MB[21]=fr==FR_OK;return fr; }
    return 1900;
}

int main(void) {
    Xil_DCacheDisable();Xil_ICacheDisable();
    for(unsigned i=0;i<64;i++) MB[i]=0;
    MB[0]=0x53445731u;MB[1]=1;MB[2]=2;
    FRESULT r=f_mount(&fs,"0:",1);
    MB[5]=r;MB[2]=r==FR_OK?1u:4u;
    for(;;) {
        unsigned cmd=MB[3];
        if(!cmd) continue;
        MB[3]=0;MB[2]=2;unsigned status=dispatch(cmd);
        MB[5]=status;MB[4]++;MB[2]=status?4u:3u;
    }
}
