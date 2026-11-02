"""Preserve R1; rebuild only application timing gate. Detector binary object unchanged."""
import shutil,subprocess
from build_road_camera import ROOT,HERE,read,write,sha

def main():
    old=read(ROOT/'offline_complete.json');rev=ROOT/'revisions/r1';rev.mkdir(parents=True,exist_ok=False)
    shutil.copytree(ROOT/'source',rev/'source');shutil.copytree(ROOT/'obj',rev/'obj')
    for name in ['road_camera.elf','offline_complete.json','camera_common.tcl','build.log']:shutil.copy2(ROOT/name,rev/name)
    shutil.copy2(HERE/'road_camera_main.c',ROOT/'source/road_camera_main.c')
    compilecmd=next(c for c in old['commands'] if '-c' in c and str(ROOT/'source/road_camera_main.c') in c)
    kernel_before=sha(ROOT/'obj/road_fp32.c.o')
    p=subprocess.run(compilecmd,capture_output=True,text=True);logs=[p.stdout+p.stderr];assert p.returncode==0,p.stderr
    linkcmd=old['commands'][-1];assert '-c' not in linkcmd and '-Wl,-build-id=none' in linkcmd
    p=subprocess.run(linkcmd,capture_output=True,text=True);logs.append(p.stdout+p.stderr);assert p.returncode==0,p.stderr
    assert sha(ROOT/'obj/road_fp32.c.o')==kernel_before
    o=dict(old);o['elf_sha256']=sha(ROOT/'road_camera.elf');o['source_sha256']={str(p.relative_to(ROOT/'source')):sha(p) for p in (ROOT/'source').rglob('*') if p.is_file()};o['revision']='r2_pause_accounting_boundary'
    write(ROOT/'offline_complete.json',o);(ROOT/'build_r2.log').write_text('\n'.join(logs))
    p=ROOT/'camera_common.tcl';code=p.read_text();assert old['elf_sha256'] in code;code=code.replace(old['elf_sha256'],o['elf_sha256']);p.write_text(code,encoding='ascii')
    # Same install path, reduced trace for the unchanged detector kernel already proved with all86 physical tensors.
    install=(ROOT/'install_camera_test.tcl').read_text();install=install.replace('} 1 3091751414 1','} 1 3091751414 0').replace('} 1\n disconnect','} 0\n disconnect')
    assert 'rc_test {02e67bab-27594c1d} 1 3091751414 0' in install and 'rc_packet $out fixed {02e67bab-27594c1d} 0' in install
    (ROOT/'install_camera_r2_test.tcl').write_text(install,encoding='ascii')
    write(ROOT/'revision_r2.json',dict(status='PAUSE_ACCOUNTING_BOUNDARY_FIXED_KERNEL_OBJECT_IDENTICAL',previous_elf_sha256=old['elf_sha256'],elf_sha256=o['elf_sha256'],
        kernel_object_sha256=kernel_before,change='Capture paused_ticks baseline immediately before detection start; idle service pauses excluded from both elapsed and pause subtraction.',
        r1_evidence_preserved=str(rev),old_physical_numerical_tests_valid_for_unchanged_kernel=True,requires_new_app_camera_readback=True))
    print('ROAD_CAMERA_R2_TIMER_GATE_COMPILED',o['elf_sha256'],flush=True)
if __name__=='__main__':main()
