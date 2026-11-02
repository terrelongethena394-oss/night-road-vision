from pathlib import Path
import csv,importlib.util,json,subprocess,sys
HERE=Path(__file__).resolve().parent
def main():
    kind=sys.argv[1];assert kind in ['full','schedule'];root=Path('E:/FPGA_Enhance_Work/road_qconv_r2_'+kind+'_20261027')
    s=importlib.util.spec_from_file_location('qcheck',HERE/'check_road_qconv.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.ROOT=root
    if kind=='schedule':m.main()
    else:
        m.invoke('csim','ROAD_QCONV_CSIM_COMPLETE');rows=list(csv.DictReader((root/'tb_all.csv').open()));assert len(rows)==66 and all(int(r['byte_differences'])==0 for r in rows)
        result=dict(status='R2_FULL_RESOLUTION_60_LAYERS_PLUS6_BOUNDARIES_CSIM_EXACT',rows=rows,source_sha256={n:m.sha(root/n) for n in ['road_qconv_hls.cpp','road_qconv_hls.h','tb_road_qconv.cpp']},hardware_access=False)
        (root/'full_csim_checked.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('ROAD_QCONV_R2_FULL_SHAPE_CSIM_PASS',flush=True)
if __name__=='__main__':main()
