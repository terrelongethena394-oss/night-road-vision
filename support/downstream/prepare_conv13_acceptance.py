"""Reuse the audited camera acceptance harness with explicit ABI/layer-count changes."""
from prepare_fp32_cpu_pack import HERE,read,write,sha
from prepare_road_conv13_runtime import ROOT
VERSION=17
SELECT_BEST_POLICY=False

def main():
    p=ROOT/'run_acceptance.py';assert not p.exists()
    c=(HERE/'run_fp32_cpu_pack_board.py').read_text()
    c=c.replace('from prepare_fp32_cpu_pack import ROOT,CURRENT,BASE,read,write,sha',"sys.path.insert(0,"+repr(str(HERE))+")\nfrom prepare_fp32_cpu_pack import CURRENT,BASE,read,write,sha\nROOT=Path('"+ROOT.as_posix()+"')")
    c=c.replace("ROOT/'native_complete.json'","ROOT/'host_complete.json'")
    c=c.replace('foreach cpu {0 1}','foreach cpu {1 2}').replace('for cpu in [0,1]','for cpu in [1,2]')
    c=c.replace('mwr 0x13800200 $cpu','mwr 0x13800120 $cpu').replace('inject $first 1 0 1','inject $first 2 0 1')
    c=c.replace('(0x524f4144,16,3,1)',f'(0x524f4144,{VERSION},3,1)').replace('m[72]==1','m[72]==cpu')
    c=c.replace('m[73]==12 and m[104]==12*(1+detail)','m[73]==(12 if cpu==1 else 51) and m[104]==(12 if cpu==1 else 51)*(1+detail)')
    for old,tag in [('_0_0','_BASE_0'),('_1_0','_NEW_0'),('_0_1','_BASE_1'),('_1_1','_NEW_1')]:c=c.replace(old,tag)
    for tag,new in [('_BASE_0','_1_0'),('_NEW_0','_2_0'),('_BASE_1','_1_1'),('_NEW_1','_2_1')]:c=c.replace(tag,new)
    for old,tag in [("['0_0']","['BASE0']"),("['1_0']","['NEW0']"),("['0_1']","['BASE1']"),("['1_1']","['NEW1']")]:c=c.replace(old,tag)
    for tag,new in [("['BASE0']","['1_0']"),("['NEW0']","['2_0']"),("['BASE1']","['1_1']"),("['NEW1']","['2_1']")]:c=c.replace(tag,new)
    # The original code's same-ARM equality guard remains intact, now1 versus2.
    assert "out/f'{name}_1_0'/n).read_bytes()==(out/f'{name}_2_0'/n)" in c
    assert "out/f'{name}_2_0'/n).read_bytes()==(original/n)" in c
    c=c.replace("result=validate(cases);write(ROOT/'validated.json',result)","result=validate(cases);original=read(ROOT/'original_baseline.json');result['actual_abi15_baseline']=original;result['speedup_actual15']=original['median']/result['timing']['2_0']['median'];write(ROOT/'validated.json',result)")
    c=c.replace("assert result['speedup_single']>=1.05,'Packing did not provide5% median gain'","assert result['speedup_single']>=1.05 and result['speedup_actual15']>=1.05,'Shared core did not provide5% median gain versus both baselines'\n  assert result['live'][1]['detection_hz']>=.9*original['live']['detection_hz'],'Camera cadence regressed'")
    c=c.replace('CPU_PACK','CONV13').replace('cpu_pack=cpu','pl_mode=cpu')
    if SELECT_BEST_POLICY:
        line="result=validate(cases);original=read(ROOT/'original_baseline.json');result['actual_abi15_baseline']=original;result['speedup_actual15']=original['median']/result['timing']['2_0']['median'];write(ROOT/'validated.json',result)"
        new="result=validate(cases);original=read(ROOT/'original_baseline.json');chosen=2 if result['speedup_single']>=1.05 else 1;result['actual_abi15_baseline']=original;result['selected_pl_mode']=chosen;result['speedup_actual15_selected']=original['median']/result['timing'][f'{chosen}_0']['median'];write(ROOT/'validated.json',result)"
        assert line in c;c=c.replace(line,new)
        c=c.replace("assert result['speedup_single']>=1.05 and result['speedup_actual15']>=1.05,'Shared core did not provide5% median gain versus both baselines'","assert result['speedup_actual15_selected']>=1.05,'Selected16-lane mode did not improve actual15 by5%'")
        c=c.replace("result['live'][1]['detection_hz']","result['live'][chosen-1]['detection_hz']")
        c=c.replace("with (ROOT/'activate.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start']","with (ROOT/'activate.log').open('w') as f:p=subprocess.run([sys.executable,str(APP/'experiment.py'),'start',str(chosen)]")
        c=c.replace("speedup_single=result['speedup_single'])","speedup_single=result['speedup_single'],selected_pl_mode=chosen)")
    p.write_text(c,encoding='utf-8')
    protocol=read(ROOT/'protocol.json');protocol.update(acceptance_script_sha256=sha(p),speed_gates='Same hardware old12 vsnew51 >=5%; actual unchanged ABI15 prebaseline vsnew51 >=5%; camera detection cadence >=90% actual15 short-window baseline. Then alternating confirmation10 per mode and confidence interval.',quality_gates='Same ARM heads/decode/boxes and first86 trace byteexact toactual15; native references; bothfull/ROI; camera/pixel/VDMA checks unchanged.')
    if SELECT_BEST_POLICY:protocol['speed_gates']='Preregistered16lane selection: choose51layers only if pilotmedian >=5% faster than12layers; otherwise choose12layers. Selected mode must improve fresh actual15 median by>=5%, camera>=90%. Independent alternating10/mode confirmation and actual15 mean-savings95%lower>0. If51chosen also require paired gain95%lower>0; selected12 must not be>5% slower than51 inconfirmation.'
    write(ROOT/'protocol.json',protocol)
    print('CONV13_ACCEPTANCE_FROZEN',sha(p),flush=True)

if __name__=='__main__':main()
