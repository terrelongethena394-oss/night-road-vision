"""Compare the candidate's board wiring with the physically checked NN8 build."""
from pathlib import Path
import hashlib
import json

ROOT=Path('E:/FPGA_Enhance_Work/camera_nn_digit_20261023')
OLD=Path('E:/FPGA_Enhance_Work/camera_nn8_20261023/prj/camera_nn.srcs/sources_1/bd/system/system.bd')
NEW=ROOT/'prj/camera_digit.srcs/sources_1/bd/system/system.bd'

def main():
    old=json.loads(OLD.read_text(encoding='utf-8'))['design']
    new=json.loads(NEW.read_text(encoding='utf-8'))['design']
    assert new['design_info']['device']=='xc7z020clg400-2'
    assert new['design_info']['validated']=='true'
    assert set(new['components'])-set(old['components'])=={'raw_digit_0','enhanced_digit_0'}
    assert set(old['components'])<=set(new['components'])
    for section in ('ports','interface_ports'):
        assert set(old[section])==set(new[section])
        for name,a in old[section].items():
            b=new[section][name]
            for k in ('direction','left','right','mode','vlnv','port_maps'):
                assert a.get(k)==b.get(k),(section,name,k)
    def edges(d,kind):
        field='ports' if kind=='nets' else 'interface_ports'
        return [set(e[field]) for e in d[kind].values()]
    for pins in edges(old,'nets'):
        assert any(pins<=n for n in edges(new,'nets')),pins
    replaced=[{'nn_input_bridge/M_AXIS','nanodce8_full_0/input_r'},
              {'nanodce8_full_0/output_r','nn_output_bridge/S_AXIS'}]
    for pins in edges(old,'interface_nets'):
        if pins not in replaced:assert any(pins<=n for n in edges(new,'interface_nets')),pins
    for a,b in [('nn_input_bridge/M_AXIS','raw_digit_0/input_r'),
                ('raw_digit_0/output_r','nanodce8_full_0/input_r'),
                ('nanodce8_full_0/output_r','enhanced_digit_0/input_r'),
                ('enhanced_digit_0/output_r','nn_output_bridge/S_AXIS'),
                ('ps7_0_axi_periph/M05_AXI','raw_digit_0/s_axi_control'),
                ('ps7_0_axi_periph/M06_AXI','enhanced_digit_0/s_axi_control')]:
        assert {a,b} in edges(new,'interface_nets'),(a,b)
    diffs={}
    for name,c in old['components'].items():
        before,after=c.get('parameters',{}),new['components'][name].get('parameters',{})
        changed={k:[before.get(k),after.get(k)] for k in set(before)|set(after) if before.get(k)!=after.get(k)}
        if changed:diffs[name]=changed
    assert set(diffs)<={'ps7_0_axi_periph','processing_system7_0'},diffs
    # Vivado serializes four previously implicit PS defaults on BD import.
    # Require the exact default values; finalization also compares ps7_init bytes.
    if 'processing_system7_0' in diffs:
        expected={'PCW_S_AXI_HP1_DATA_WIDTH':'64','PCW_S_AXI_HP2_DATA_WIDTH':'64',
                  'PCW_S_AXI_HP3_DATA_WIDTH':'64','PCW_IRQ_F2P_MODE':'DIRECT'}
        assert diffs['processing_system7_0']=={k:[None,{'value':v}] for k,v in expected.items()}
    assert set(diffs['ps7_0_axi_periph'])=={'NUM_MI'}
    assert new['components']['ps7_0_axi_periph']['parameters']['NUM_MI']['value']=='7'
    for comp,entry in old['addressing'].items():
        for space,v in entry['address_spaces'].items():
            for name,segment in v['segments'].items():
                assert segment==new['addressing'][comp]['address_spaces'][space]['segments'][name]
    segments=new['addressing']['/processing_system7_0']['address_spaces']['Data']['segments']
    for name,port,offset in [('raw_digit_0','M05','0x43C30000'),('enhanced_digit_0','M06','0x43C40000')]:
        assert segments['SEG_'+name+'_Reg']==dict(address_block='/'+name+'/s_axi_control/Reg',offset=offset,range='64K')
        clock={'processing_system7_0/FCLK_CLK0',name+'/ap_clk','ps7_0_axi_periph/'+port+'_ACLK'}
        reset={'rst_ps7_0_100M/peripheral_aresetn',name+'/ap_rst_n','ps7_0_axi_periph/'+port+'_ARESETN'}
        assert any(clock<=n for n in edges(new,'nets'))
        assert any(reset<=n for n in edges(new,'nets'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(status='PASS',baseline=str(OLD),candidate=str(NEW),
                preserved_external_ports=True,preserved_original_scalar_wiring=True,
                preserved_original_address_map=True,original_component_parameter_changes=diffs,
                new_core_addresses=['0x43C30000','0x43C40000'],stream_clock_mhz=100,
                shared_digit_weights_sha256=sha(Path('E:/FPGA_Enhance_Work/digit_recognition_20261023/hls/digit_weights.h')))
    (ROOT/'integration_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('DIGIT_BOARD_INTEGRATION_AUDIT_PASS')

if __name__=='__main__':main()
