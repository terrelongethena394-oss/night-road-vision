"""Prepare concrete full-network RAM-only A/B test and checksum its artifacts."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path('E:/FPGA_Enhance_Work/road_hybrid_20261027_r1')
CAM=Path('E:/FPGA_Enhance_Work/road_camera_20261027')
NN=Path('E:/FPGA_Enhance_Work/road_arm_prototype_20261026')
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fnv(raw):
    h=2166136261
    for v in raw:h=((h^v)*16777619)&0xffffffff
    return h
def main():
    proof=json.loads((ROOT/'arm_complete.json').read_text());assert sha(ROOT/'road_hybrid.elf')==proof['elf_sha256']
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=False);shutil.copy2(NN/'weights.f32',runtime/'weights.f32')
    fixtures=json.loads((NN/'export_complete.json').read_text())['fixtures'];first=fixtures[0]['name']
    for f in fixtures:
        folder=runtime/'cases'/f['name'];folder.mkdir(parents=True)
        shutil.copy2(NN/'cases'/f['name']/'input400.u32',folder/'input400.u32')
    common=(CAM/'camera_common.tcl').read_text().replace('!=10','!=11').replace('47ddf53348eacfde4f4956f53fe39b2d0637c189e8666cf6dfb476e94dd93166',proof['elf_sha256']).replace('676f575fed31e20e0b6b5a4db0b5bcc62718686e32756c17ce552685b9257427',proof['bit_sha256'])
    old='proc word {a} {return [expr {[lindex [mrd -value $a] 0]+0}]}'
    new='''proc word {a} {
 if {[catch {mrd -value $a} v]} {
  if {![string match {*Invalid context*} $v]} {error $v}
  targets -set -filter {name =~ "ARM*#0"} -timeout 10
  set v [mrd -value $a]
 }
 return [expr {[lindex $v 0]+0}]
}'''
    assert common.count(old)==1;common=common.replace(old,new)
    (ROOT/'camera_common.tcl').write_text(common,encoding='ascii')
    entries=' '.join('{%s} {%d %d}'%(f['name'],i+1,fnv((NN/'cases'/f['name']/'input400.u32').read_bytes())) for i,f in enumerate(fixtures))
    text=r'''source [file join [file dirname [file normalize [info script]]] camera_common.tcl]
set out $root/physical_full_r1
if {[file exists $out]} {error "Preserve earlier full-network readback"}
set cases [dict create @CASES@]
set first {@FIRST@}
proc compact {folder} {
 if {[file exists $folder]} {error "Preserve previous packet"}
 file mkdir $folder
 set n [word 0x138000d0]
 if {$n<0 || $n>300} {error "Invalid detector count"}
 mrd -bin -file $folder/mailbox80.bin 0x13800000 80
 mrd -bin -file $folder/decoded.f32 0x16300000 56700
 mrd -bin -file $folder/head0.f32 0x16400000 44800
 mrd -bin -file $folder/head1.f32 0x1642bc00 11200
 mrd -bin -file $folder/head2.f32 0x16436b00 2800
 if {$n>0} {mrd -bin -file $folder/boxes400.f32 0x16200000 [expr {$n*6}]} else {close [open $folder/boxes400.f32 w]}
}
if {[catch {
 connect -url tcp:127.0.0.1:3121
 puts [targets]
 targets -set -filter {name =~ "APU*"} -timeout 10
 rst -system
 after 1000
 fpga -file $root/display.bit
 targets -set -filter {name =~ "ARM*#0"} -timeout 10
 source $root/ps7_init.tcl
 ps7_init
 ps7_post_config
 loadhw -hw $root/display.xsa
 dow $root/road_hybrid.elf
 con
 set ready 0
 for {set i 0} {$i<400} {incr i} {
  after 100
  if {[word 0x13800000]==0x524F4144 && [word 0x13800004]==11} {
   rc_check
   if {[word 0x13800008]==1 && [word 0x138000a0]==0x5640 && [word 0x13800078]==0x7084} {set ready 1;break}
  }
 }
 if {!$ready} {error "Hybrid camera initialization failed"}
 puts "ROAD_HYBRID_STAGE camera_ready"
 dow -data $root/runtime/weights.f32 0x11000000
 catch {con}
 file mkdir $out
 lassign [dict get $cases $first] photo expected
 foreach {mode label} {0 cpu 1 hybrid} {
  mwr 0x13800120 $mode
  for {set j 0} {$j<4} {incr j} {
   rc_test $first $photo $expected 0
   mrd -bin -file $out/${label}_timing$j.bin 0x13800000 80
   puts "ROAD_HYBRID_TIMING $label run=$j calls=[word 0x13800124]"
  }
  if {$mode==0} {compact $out/cpu_first} else {compact $out/$first}
 }
 # A separate traced run is excluded from the timing statistics.
 rc_test $first $photo $expected 1
 rc_packet $out/first_hybrid_full fixed $first 1
 mrd -bin -file $out/first_hybrid_full/mailbox80.bin 0x13800000 80
 dict for {name shape} $cases {
  if {$name eq $first} {continue}
  lassign $shape photo expected
  rc_test $name $photo $expected 0
  compact $out/$name
  puts "ROAD_HYBRID_FIXED_PACKET $name calls=[word 0x13800124]"
 }
 set f [open $out/COMPLETE.txt w]
 puts $f "ROAD_HYBRID_FULL_TEST_READBACK_COMPLETE"
 close $f
 disconnect
 puts "ROAD_HYBRID_FULL_TEST_READBACK_COMPLETE"
} why opts]} {
 puts stderr "ROAD_HYBRID_FULL_TEST_FAILED: $why"
 if {[dict exists $opts -errorinfo]} {puts stderr [dict get $opts -errorinfo]}
 catch {disconnect}
 exit 1
}
exit
'''
    text=text.replace('@CASES@',entries).replace('@FIRST@',first)
    (ROOT/'test_full_ram.tcl').write_text(text,encoding='ascii')
    context=dict(elf_sha256=proof['elf_sha256'],bit_sha256=proof['bit_sha256'],weights_sha256=sha(runtime/'weights.f32'),hardware_access=False)
    (ROOT/'test_context.json').write_text(json.dumps(context,indent=2),encoding='utf-8')
    files=[p for p in runtime.rglob('*') if p.is_file()]+[ROOT/n for n in ['road_hybrid.elf','display.bit','display.xsa','ps7_init.tcl','test_full_ram.tcl','camera_common.tcl']]
    (ROOT/'runtime_checksums.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in files},indent=2),encoding='utf-8')
    print('ROAD_HYBRID_FULL_TEST_PREPARED',len(files),flush=True)
if __name__=='__main__':main()
