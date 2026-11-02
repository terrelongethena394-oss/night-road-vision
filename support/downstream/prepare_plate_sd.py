"""Create a new PC-side Zynq SD image; never access removable media."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, struct, subprocess

BASE = Path('E:/FPGA_Enhance_Work')
BOARD = BASE/'camera_plate_guarded_20261026'
OLD = BASE/'camera_nn_sd_20261018'
OUT = BASE/'plate_sd_20261026'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    assert not OUT.exists(), 'Preserve existing package'
    deployed = json.loads((BOARD/'board_deployed.json').read_text(encoding='utf-8'))
    assert deployed['status'] == 'PLATE_GUARDED_OFFLINE_ACCEPTED_AND_BOARD_VERIFIED'
    assert sha(BOARD/'camera.elf') == deployed['elf_sha256']
    assert sha(BOARD/'camera.bit') == deployed['bit_sha256']
    prior = json.loads((OLD/'boot_image_validation.json').read_text())
    assert prior['image_checks'] == 'PASS' and sha(OLD/'fsbl.elf') == prior['sha256']['fsbl.elf']
    ps_proof = {}
    for name in ['ps7_init.c','ps7_init.h']:
        assert sha(OLD/'vitis_ws/nn_fsbl/src'/name) == sha(BOARD/name)
        ps_proof[name] = sha(BOARD/name)
    OUT.mkdir()
    for src,name in [(OLD/'fsbl.elf','fsbl.elf'),(BOARD/'camera.bit','camera.bit'),(BOARD/'camera.elf','camera.elf')]:
        shutil.copy2(src,OUT/name)
        assert sha(src)==sha(OUT/name)
    (OUT/'boot.bif').write_text('the_ROM_image:\n{\n    [bootloader] fsbl.elf\n    camera.bit\n    camera.elf\n}\n',encoding='ascii')
    run = subprocess.run(['E:/Xilinx/Vitis/2020.2/bin/bootgen.bat','-arch','zynq','-image','boot.bif','-o','BOOT.BIN'],cwd=OUT,capture_output=True,text=True)
    (OUT/'bootgen.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    assert run.returncode == 0 and (OUT/'BOOT.BIN').exists(), run.stdout+run.stderr
    spec = importlib.util.spec_from_file_location('prior_boot_parser',OLD/'verify_nn_sd.py')
    parser = importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    data = (OUT/'BOOT.BIN').read_bytes()
    word = lambda offset: struct.unpack_from('<I',data,offset)[0]
    assert word(0x20)==0xAA995566 and word(0x24)==0x584C4E58
    assert sum(struct.unpack_from('<11I',data,0x20)) & 0xffffffff == 0xffffffff
    iht,pht=word(0x98),word(0x9c)
    assert word(iht+4)==3
    partitions=[]
    for i,name in enumerate(['fsbl.elf','camera.bit','camera.elf']):
        p=struct.unpack_from('<16I',data,pht+64*i)
        assert sum(p)&0xffffffff == 0xffffffff
        length,load,entry,offset=p[2]*4,p[3],p[4],p[5]*4
        assert offset+length<=len(data)
        payload=data[offset:offset+length]
        if name.endswith('.elf'):
            expected_entry,segments=parser.elf_segments(OUT/name)
            assert entry==expected_entry
            for address,content in segments:
                relative=address-load
                assert relative>=0 and payload[relative:relative+len(content)]==content
        else:
            bit=parser.bit_payload(OUT/name)
            swapped=b''.join(bit[j:j+4][::-1] for j in range(0,len(bit),4))
            assert payload[:len(bit)] in (bit,swapped)
        partitions.append(dict(name=name,load=load,entry=entry,bytes=length,source_bytes_match=True))
    assert partitions[0]['load']==0 and partitions[0]['bytes']<0x30000
    assert partitions[2]['load']==0x100000
    result=dict(status='BOOT_IMAGE_HEADERS_AND_ALL_PARTITION_BYTES_VERIFIED',
                architecture='Zynq-7000',source_board=str(BOARD),fsbl_source=str(OLD/'fsbl.elf'),
                ps_init_hashes_match=ps_proof,sha256={p.name:sha(p) for p in OUT.glob('*') if p.is_file()},
                partitions=partitions,sd_written=False,physical_sd_boot='NOT_YET_TESTED',
                scope='Seven-character blue plates in fixed ROI; ARM NEON OCR plus PL enhancement')
    (OUT/'boot_image_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PLATE_SD_IMAGE_VERIFIED',len(data),sha(OUT/'BOOT.BIN'),flush=True)

if __name__=='__main__':main()
