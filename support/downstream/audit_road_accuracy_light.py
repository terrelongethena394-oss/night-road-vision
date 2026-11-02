"""Brightness audit independent of detection outcomes; flag period mistakes."""
import collections
from PIL import Image,ImageDraw
from road_accuracy_common import *
from road_numpy_eval import evaluate

def mean_y(a):
    z=a.astype(np.uint32);return float(((54*z[:,:,0]+183*z[:,:,1]+19*z[:,:,2])/256).mean())
def main():
    rows=read(ROOT/'fresh/manifest.json');flags=[];audit=[]
    for r in rows:
        _,a=sensor400(ROOT/'fresh/images'/r['name']);v=mean_y(a);audit.append(dict(name=r['name'],timeofday=r['timeofday'],mean_y=v,low_brightness=v<=48))
        if r['timeofday']=='night' and v>=85:flags.append((r['name'],v,a))
    write(ROOT/'brightness_audit.json',dict(status='POST_TEST_DATA_LABEL_AUDIT_NOT_NEW_INDEPENDENT_EVIDENCE',threshold=48,definition='Mean fixed Y=(54R+183G+19B)/256 on the unenhanced400x240 board input',low_brightness_counts=dict(collections.Counter(r['timeofday'] for r in audit if r['low_brightness'])),bright_night_flag_count=len(flags),flag_rule='Night metadata but mean>=85; heuristic flags, not automatic relabelling',confirmed_visual_mismatch='b9117002-f2ff0c31.jpg looks daytime despite night metadata',rows=audit))
    for page in range((len(flags)+19)//20):
        canvas=Image.new('RGB',(1000,5*142),'white');d=ImageDraw.Draw(canvas)
        for i,(name,v,a) in enumerate(flags[page*20:(page+1)*20]):
            x=(i%4)*250;y=(i//4)*142;canvas.paste(Image.fromarray(a).resize((250,120)),(x,y+20));d.text((x+2,y+3),name[:20]+' '+str(int(v)),fill='black')
        canvas.save(ROOT/f'bright_night_flags_{page}.png')
    gate={r['name'] for r in audit if r['timeofday']=='night' and r['low_brightness']}
    scores={}
    for tag in ['baseline','candidate']:
        subset=[r for r in read(ROOT/'native'/(tag+'_predictions.json')) if r['name'] in gate];scores[tag]=evaluate(subset)
    write(ROOT/'lowlight_posthoc_diagnostic.json',dict(images=len(gate),scores=scores,posthoc=True,not_new_independent_test=True))
    print('BRIGHTNESS_AUDIT',len(gate),'lowlight night-labelled;',len(flags),'bright flags; descriptive carAP',[scores[k]['classes']['car']['ap50'] for k in scores],flush=True)

if __name__=='__main__':main()
