from pathlib import Path
import json
p=Path('E:/FPGA_Enhance_Work/model_upgrade_20261023/student_training_split.json')
j=json.loads(p.read_text(encoding='utf-8'))
for k,v in j.items():print(k,len(v) if isinstance(v,(list,dict)) else v,str(v)[:350])
print('LOWFILES',len(list((p.parent/'dataset/our485/low').glob('*'))))
