"""Predeclare convenience sample before download/annotation/model inference."""
from pathlib import Path
import json,urllib.request,urllib.parse,hashlib,concurrent.futures,time
from recognition_upgrade_common import ROOT,write,sha
OUT=ROOT/'fresh_house_photos'
TITLES=[(2,'Husnummer Nobelgatan 2.jpg'),(2,'House 2, double marked, Guanajuato.jpg'),(3,'Hausnummer 3.JPG'),(3,'Number three ornament house.jpg'),(6,'6 Corallejo.jpg'),(6,'Glogera 6 numer domu.jpg'),(7,'Hausnummer 7.JPG'),(7,'House number 7, Guanajuato.jpg')]
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FPGAStudentResearch/1.0 (local educational image evaluation)'}),timeout=20) as r:return r.read()
def main():
    OUT.mkdir(exist_ok=True);manifest=OUT/'sampling_protocol.json';assert not manifest.exists()
    write(manifest,dict(status='TITLES_FIXED_BEFORE_FETCH_OR_INFERENCE',files=[dict(truth=k,title=t,page='https://commons.wikimedia.org/wiki/File:'+urllib.parse.quote(t.replace(' ','_'))) for k,t in TITLES],selection='Convenience sample from public house-number categories, two titles each for2,3,6,7 chosen for focus on signs, without reading any model output. Not random population sampling.',annotation='Before inference, manually mark one visible Arabic digit in full photo. If repeated same digit choose largest then leftmost. Reject only corrupt/nonphotographic/no unambiguous Arabic digit/previous-source duplicate; keep rejection log and no replacement after predictions.',candidate='run03 fixed training12k, validation-selected before evaluation; no new photo fitting or checkpoint selection',evaluation='Supplemental normal-light given-ROI recognition only; report all samples and old/new controls, no night or automatic detection claim. Keep models/thresholds unchanged after looking at these results.'))
    for i,(k,title) in enumerate(TITLES):
        page='https://commons.wikimedia.org/wiki/File:'+urllib.parse.quote(title.replace(' ','_'))
        query=urllib.parse.urlencode(dict(action='query',format='json',prop='imageinfo',iiprop='url|extmetadata',titles='File:'+title))
        try:
            info=json.loads(get('https://commons.wikimedia.org/w/api.php?'+query));row=next(iter(info['query']['pages'].values()));ii=row['imageinfo'][0]
            ext=ii.get('extmetadata',{});original=get(ii['url']);p=OUT/f'photo_{i}.jpg';p.write_bytes(original)
            write(OUT/f'photo_{i}.json',dict(title=title,truth=k,page=page,url=ii['url'],sha256=sha(p),path=str(p),metadata=ext))
            print('FRESH_PHOTO_DOWNLOADED',i,len(original),flush=True)
        except Exception as e:
            write(OUT/f'photo_{i}_unavailable.json',dict(title=title,truth=k,page=page,error=repr(e)));print('PHOTO_UNAVAILABLE',i,repr(e),flush=True)
    print('FRESH_PHOTO_FETCH_FINISHED',flush=True)
if __name__=='__main__':main()
