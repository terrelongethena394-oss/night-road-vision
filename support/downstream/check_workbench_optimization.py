from pathlib import Path
import py_compile
from car_roi_delivery_common import BASE,read,write
for name in ['photo_station_core.py','camera_station_core.py','camera_preview_stream.py','benchmark_workbench_optimization.py']:
    py_compile.compile(str(Path(__file__).with_name(name)),doraise=True)
out=BASE/'workbench_optimization_20261031_r1'
write(out/'initial_cache_source_correction.json',dict(status='INITIAL_SCREEN_EXCLUDED_WRONG_TRAINING_VARIANT',
    excluded=str(out/'confidence_screen.json'),reason='First cache candidate was the rejected augmentation variant, not deployed matched_raw.',
    valid_current_model_screen=str(out/'current_model_screen/confidence_screen.json'),deployed_baseline_counts_checked=True))
print('OPTIMIZATION_PYTHON_COMPILE_PASS',flush=True)
