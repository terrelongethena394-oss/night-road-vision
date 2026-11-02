"""Manufactured host fixtures test validator rejection paths; NEVER board evidence."""
from pathlib import Path
import json,struct
from validate_road_conv_board import validate,fnv
ROOT=Path('E:/FPGA_Enhance_Work/road_conv_board_20261027')
def main():
    fixtures=json.loads((ROOT/'future_board_test/fixtures.json').read_text())
    elf=json.loads((ROOT/'arm_probe/compile_complete.json').read_text())['elf_sha256']
    mock=ROOT/'framework_selfcheck_mock_NOT_BOARD';mock.mkdir(exist_ok=False)
    (mock/'context.txt').write_text('source=physical_jtag_readback\nelf_sha256='+elf+'\nMOCK_NOT_BOARD_EVIDENCE\n')
    for seq,c in enumerate(fixtures,1):
        d=mock/c['name'];d.mkdir()
        m=[0]*64;m[:3]=[0x52435033,1,3];m[4]=seq;m[7:12]=[c[k] for k in ['h','w','ic4','oc4','stride']]
        m[12]=m[14]=c['input_fnv32'];m[13]=m[15]=c['packed_fnv32'];m[16]=1000000;m[17]=c['output_words']
        data=Path(c['expected']).read_bytes();m[20]=m[21]=fnv(data);m[22:25]=[8,1,0]
        for j in range(4):m[32+6*j:38+6*j]=[2000,0,1000,0,900,0]
        (d/'mailbox.bin').write_bytes(struct.pack('<64I',*m))
        (d/'cpu.f32').write_bytes(data);(d/'pl.f32').write_bytes(data)
        (d/'input.f32').write_bytes(Path(c['input']).read_bytes());(d/'packed.f32').write_bytes(Path(c['packed']).read_bytes())
    result=validate(mock,fixtures,elf);assert len(result['results'])==11
    first=mock/fixtures[0]['name'];original=(first/'mailbox.bin').read_bytes();out=(first/'pl.f32').read_bytes();input_bytes=(first/'input.f32').read_bytes()
    rejected=[]
    def fail(name):
        try:validate(mock,fixtures,elf)
        except AssertionError:rejected.append(name);return
        raise AssertionError('corruption accepted: '+name)
    for name,index,value in [('wrong_magic',0,0),('stale_sequence',4,0),('job_failed',2,4),('wrong_shape',7,2),('wrong_hash',14,1),('no_timer',16,0),('guard_corrupted',23,0),('ip_return_failed',24,1),('zero_duration',32,0),('wait_longer_than_total',36,2000)]:
        m=list(struct.unpack('<64I',original));m[index]=value;(first/'mailbox.bin').write_bytes(struct.pack('<64I',*m));fail(name)
    (first/'mailbox.bin').write_bytes(original)
    (first/'pl.f32').write_bytes(out[:-4]);fail('truncated_output');(first/'pl.f32').write_bytes(out)
    corrupted=struct.pack('<f',12345.0)+out[4:];(first/'pl.f32').write_bytes(corrupted)
    m=list(struct.unpack('<64I',original));m[21]=fnv(corrupted);(first/'mailbox.bin').write_bytes(struct.pack('<64I',*m));fail('wrong_numeric_output_even_with_matching_hash')
    (first/'pl.f32').write_bytes(out);(first/'mailbox.bin').write_bytes(original)
    (first/'input.f32').write_bytes(b'\x01'+input_bytes[1:]);fail('wrong_input_readback');(first/'input.f32').write_bytes(input_bytes)
    assert len(rejected)==13
    receipt=dict(status='HOST_VALIDATOR_SELFCHECK_ONLY_NOT_BOARD_EVIDENCE',positive_manufactured_cases=11,corruption_rejections=rejected,hardware_access=False)
    (ROOT/'validator_selfcheck.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('HOST_VALIDATOR_SELFCHECK_PASS 11 manufactured cases, 13 corruptions rejected; NOT_BOARD_EVIDENCE')
if __name__=='__main__':main()
