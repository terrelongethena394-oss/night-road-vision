"""2020.2 generated-IP timestamp overflow workaround, project-local only."""
from pathlib import Path
import re,sys
from train_real_digit_cnn import OUT

revision=sys.argv[1] if len(sys.argv)>1 else 'hls_corrected'
assert revision in ('hls_corrected','hls_score64')
root=(OUT/revision/'real_cnn_project/solution_100mhz/impl/ip').resolve()
assert root.is_relative_to(OUT.resolve())
p=root/'run_ippack.tcl';text=p.read_text(encoding='utf-8')
assert 'set SubcoreFiles [sort_file_names [glob -nocomplain subcore/*]]' in text
assert not list((root/'subcore').iterdir()),'Unexpected generated subcores'
assert re.search(r'^set enable_xo_gen false\s*$',text,re.M)
text,n=re.subn(r'^set Revision\s+"[0-9]+"','set Revision "1"',text,flags=re.M)
assert n==1
(root/'run_ippack_revision1.tcl').write_text(text,encoding='utf-8')
print('REAL_CNN_LOCAL_REVISION_SCRIPT_READY',flush=True)
