"""Negative controls on COPIES of physical readback, never fabricated board passes."""
from pathlib import Path
import shutil,struct
from road_arm_common import ROOT,read,write
from validate_road_arm_probe import validate
def main():
    name=read(ROOT/'export_complete.json')['fixtures'][0]['name'];src=ROOT/('board_readback_r2_'+name);out=ROOT/'validator_negative_controls'
    shutil.copytree(src,out);validate(out,name);checks=[]
    def reject(label):
        try:validate(out,name)
        except AssertionError:checks.append(dict(case=label,rejected=True));return
        raise RuntimeError('Validator incorrectly accepted '+label)
    p=out/'mailbox.bin';original=p.read_bytes();data=bytearray(original);data[16*4]^=1;p.write_bytes(data);reject('wrong_input_hash');p.write_bytes(original)
    p=out/'context.txt';original=p.read_bytes();p.write_text(original.decode().replace('elf_sha256=','elf_sha256=BAD_'));reject('wrong_firmware_identity');p.write_bytes(original)
    p=out/'all_layers.f32'
    with p.open('r+b') as f:
        original=f.read(4);value=struct.unpack('<f',original)[0];f.seek(0);f.write(struct.pack('<f',value+1))
    reject('corrupted_intermediate_layer')
    with p.open('r+b') as f:f.write(original)
    p=out/'boxes400.f32';original=p.read_bytes();data=bytearray(original);struct.pack_into('<f',data,5*4,99.);p.write_bytes(data);reject('wrong_output_class');p.write_bytes(original)
    p=out/'timing1.bin';original=p.read_bytes();data=bytearray(original);struct.pack_into('<I',data,4*4,0);p.write_bytes(data);reject('stale_job_sequence');p.write_bytes(original)
    validate(out,name)
    write(ROOT/'validator_selfcheck.json',dict(status='PHYSICAL_READBACK_VALIDATOR_REJECTS_ALL5_CORRUPTED_COPY_CONTROLS',checks=checks,
          note='Copies of actual readback deliberately corrupted for validator tests; not additional physical runs. Original physical evidence untouched.',board_written=False))
    print('ROAD_PROBE_VALIDATOR_NEGATIVE_CONTROLS_PASS',len(checks),flush=True)
if __name__=='__main__':main()
