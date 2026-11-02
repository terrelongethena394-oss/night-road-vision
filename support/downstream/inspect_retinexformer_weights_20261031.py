from pathlib import Path
import urllib.request,re,json
ROOT=Path('E:/FPGA_Enhance_Work/retinexformer_reference_20261031_r1')
url='https://drive.google.com/drive/folders/1ynK5hfQachzc8y96ZumhkPPDXzHJwaQV'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(req,timeout=35) as r:data=r.read()
(ROOT/'weights_folder.html').write_bytes(data)
text=data.decode('utf-8')
for match in re.finditer('LOL_v[12]|\.pth',text):
    print(text[max(0,match.start()-180):match.end()+180].encode('ascii','backslashreplace').decode())
print('BYTES',len(data))
