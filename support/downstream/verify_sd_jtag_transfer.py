from pathlib import Path
import json,sys,zlib,hashlib
ROOT=Path('E:/FPGA_Enhance_Work/plate_sd_20261026/jtag_writer')
def sha(data):return hashlib.sha256(data).hexdigest()
def words(path):return [int(s,0) for s in Path(path).read_text().split()]
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def data_exact(path,n):
    b=Path(path).read_bytes();assert len(b)==(n+3)//4*4
    return b[:n]
def main():
    mode=sys.argv[1];model=json.loads((ROOT/'writer.json').read_text())
    assert sha((ROOT/'sd_jtag_writer.elf').read_bytes())==model['elf_sha256']
    boot=(ROOT.parent/'BOOT.BIN').read_bytes()
    assert sha(boot)==model['boot_sha256'] and len(boot)==model['boot_bytes']
    assert zlib.crc32(boot)==model['boot_crc32']
    if mode=='backup':
        assert 'SD_OLD_BOOT_BACKED_UP_TO_PC_NO_NEW_FILE_WRITTEN' in (ROOT/'probe_card.log').read_text()
        w=words(ROOT/'card_backup/probe_mailbox.txt');assert w[0]==0x53445731 and w[5]==0 and w[6]==2
        old=data_exact(ROOT/'card_backup/old_boot_padded.bin',w[7]);assert zlib.crc32(old)==w[8]
        assert w[7]==w[10] and w[9] in [0,1] and w[11] in [1,2,3]
        (ROOT/'card_backup/BOOT.BIN.original').write_bytes(old)
        d=dict(status='OLD_BOOT_FULL_BYTES_SAVED_AND_CRC_VERIFIED_BEFORE_ANY_NEW_FILE_WRITE',exists=bool(w[9]),bytes=len(old),sha256=sha(old),crc32=w[8],sd_backup_name=f'B{w[19]:07d}.BIN',backup_index=w[19],filesystem=w[11])
        write(ROOT/'card_backup/backup_verified.json',d)
        (ROOT/'card_backup/backup_verified.tcl').write_text(f'set old_bytes {len(old)}\nset old_crc {w[8]}\nset backup_index {w[19]}\n',encoding='ascii')
        print(json.dumps(d,ensure_ascii=True),flush=True)
    elif mode=='stage':
        assert 'SD_TEMP_FILE_WRITTEN_AND_READ_BACK_OLD_BOOT_NOT_REPLACED' in (ROOT/'stage_card.log').read_text()
        w=words(ROOT/'staged_mailbox.txt');assert w[0]==0x53445731 and w[5]==0 and w[6]==4
        b=data_exact(ROOT/'staged_readback_padded.bin',w[7]);assert b==boot and w[8]==zlib.crc32(b)
        write(ROOT/'staged_verified.json',dict(status='STAGED_SD_FILE_ALL_BYTES_AND_SHA256_MATCH_BOOT_IMAGE',bytes=len(b),sha256=sha(b)))
        (ROOT/'staged_verified.tcl').write_text(f'set verified_bytes {len(b)}\nset verified_crc {zlib.crc32(b)}\n',encoding='ascii')
        print('SD_STAGED_ALL_BYTES_SHA256_EXACT',sha(b),flush=True)
    elif mode=='final':
        assert 'SD_BOOT_AND_OLD_BACKUP_READ_BACK_CARD_UNMOUNTED' in (ROOT/'commit_card.log').read_text()
        w=words(ROOT/'final_mailbox.txt');assert w[0]==0x53445731 and w[5]==0 and w[6]==6
        new=data_exact(ROOT/'final_readback_padded.bin',w[7]);assert new==boot and zlib.crc32(new)==w[8]
        d=json.loads((ROOT/'card_backup/backup_verified.json').read_text());b=words(ROOT/'backup_mailbox.txt')
        old=data_exact(ROOT/'card_backup/sd_backup_readback_padded.bin',b[7])
        assert sha(old)==d['sha256'] and old==(ROOT/'card_backup/BOOT.BIN.original').read_bytes()
        u=words(ROOT/'unmounted_mailbox.txt');assert u[5]==0 and u[6]==8 and u[21]==1
        receipt=dict(status='SD_BOOT_WRITTEN_VIA_JTAG_HELPER_AND_READBACK_VERIFIED',boot_bytes=len(new),boot_sha256=sha(new),old_boot_backup=d,sd_written=True,filesystem_unmounted=True,physical_sd_cold_boot='NOT_YET_TESTED',method='JTAG stages baremetal ARM FatFs helper; PS SD0 writes files. No formatting or Flash access.')
        write(ROOT.parent/'sd_write_receipt.json',receipt)
        print(json.dumps(receipt,ensure_ascii=True),flush=True)
    else:raise ValueError(mode)
if __name__=='__main__':main()
