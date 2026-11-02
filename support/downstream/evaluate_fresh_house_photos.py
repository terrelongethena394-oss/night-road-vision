"""One frozen-model pass on all available predeclared, annotated new photos."""
from pathlib import Path
import json,re
import numpy as np
from PIL import Image,ImageOps,ImageDraw
from recognition_upgrade_common import ROOT,BASE,normalize_np,sha,write
from evaluate_recognition_upgrade import native
def main():
    run=ROOT/'run03';freeze=json.loads((run/'frozen_candidate.json').read_text())
    assert sha(freeze['model'])==freeze['sha256']
    root=ROOT/'fresh_house_photos';ann=json.loads((root/'annotations.json').read_text())
    out=run/'fresh_photos';out.mkdir(exist_ok=True);assert not (out/'results.json').exists()
    x=[];rows=[];credits=[];preview=Image.new('RGB',(400,150*len(ann['rows'])),'white');draw=ImageDraw.Draw(preview)
    for j,a in enumerate(ann['rows']):
        p=root/f'photo_{a["id"]}.jpg';assert sha(p)==a['image_sha256']
        image=Image.open(p).convert('RGB');box=a['box'];assert 0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height
        crop=np.array(image.crop(box));crop[:,:,0]&=248;crop[:,:,1]&=252;crop[:,:,2]&=248
        u=crop.astype(np.uint32);g=((77*u[:,:,0]+150*u[:,:,1]+29*u[:,:,2]+128)>>8).astype(np.uint8)
        bg=int(np.median(np.concatenate([g[0],g[-1],g[:,0],g[:,-1]])))
        small=ImageOps.contain(Image.fromarray(g),(20,24),Image.Resampling.LANCZOS);canvas=Image.new('L',(28,28),bg);canvas.paste(small,((28-small.width)//2,(28-small.height)//2))
        x.append(np.array(canvas));meta=json.loads((root/f'photo_{a["id"]}.json').read_text());ext=meta['metadata']
        get=lambda key:re.sub('<[^>]+>','',ext.get(key,{}).get('value',''))
        credits.append(dict(id=a['id'],title=meta['title'],page=meta['page'],author=get('Artist'),license=get('LicenseShortName'),license_url=get('LicenseUrl'),modifications='Manual digit crop, RGB565 conversion, gray conversion, resize and margin. Derived crops retain source image license.'))
        cropimage=Image.fromarray(crop);cropimage.thumbnail((120,120));preview.paste(cropimage,(0,j*150));preview.paste(canvas.resize((112,112)),(140,j*150))
        draw.text((265,j*150+10),f'id {a["id"]}, truth {a["truth"]}',fill='black')
        rows.append(dict(id=a['id'],truth=a['truth'],box=box,page=meta['page']))
    x=np.stack(x);xn=normalize_np(x)
    for name,exe,z in [('old_raw',BASE/'digit_arm_reference_i32_20261026/digit_arm_host.exe',x),('old_normalized',BASE/'digit_arm_reference_i32_20261026/digit_arm_host.exe',xn),('new_normalized',run/'native/digit_arm_host.exe',xn)]:
        s=native(exe,z,out,name)
        for r,pred in zip(rows,s.argmax(1)):r[name]=int(pred)
    for j,r in enumerate(rows):draw.text((265,j*150+35),f'old {r["old_raw"]}, norm {r["old_normalized"]}\nnew {r["new_normalized"]}',fill='black')
    preview.save(out/'all_cases.png');write(out/'credits.json',credits)
    result=dict(status='ALL_AVAILABLE_NEW_PHOTOS_REPORTED_NO_FITTING',n=len(rows),cases=rows,correct={k:sum(r[k]==r['truth'] for r in rows) for k in ['old_raw','old_normalized','new_normalized']},model_sha256=freeze['sha256'],annotations_sha256=sha(root/'annotations.json'),sampling_protocol_sha256=sha(root/'sampling_protocol.json'),unavailable_ids=ann['unavailable_ids'],limitations=['Convenience sample of three new photos with manually annotated given digit rectangles, only digits2 and6. Not a population accuracy estimate.','Five predeclared files unavailable HTTP429 before inference, no replacement based on predictions.','RGB565 conversion precedes the same contain20x24/border-median sizing as Chars74K; not a full camera-frame preprocessing test.','No enhancement, detection or actual night performance claim. No post-result crop or threshold changes.'])
    write(out/'results.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
