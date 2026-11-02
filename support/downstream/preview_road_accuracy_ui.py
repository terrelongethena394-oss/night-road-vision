"""Host-render ABI23 layout; never label this as a physical-board capture."""
import struct,subprocess
from PIL import Image
from road_accuracy_common import *
APP=ROOT/'firmware'
def main():
    base={Path(r['name']).stem:r for r in read(ROOT/'native/baseline_predictions.json')};new={Path(r['name']).stem:r for r in read(ROOT/'native/candidate_predictions.json')}
    out=ROOT/'host_ui_preview';out.mkdir(exist_ok=True)
    for c in read(APP/'cases.json'):
        folder=out/c['name'];folder.mkdir(exist_ok=True);case=APP/'runtime/cases'/c['name']
        if c['name']=='control_black':a=b=np.empty((0,6),np.float32)
        else:
            a=np.asarray(base[c['name']]['detections'],np.float32).reshape(-1,6);a=a[a[:,4]>=.25]
            b=np.asarray(new[c['name']]['detections'],np.float32).reshape(-1,6);b=b[b[:,4]>=.25]
        a.astype('<f4').tofile(folder/'baseline.f32');b.astype('<f4').tofile(folder/'new.f32')
        ui=[0,c['photo'],c['photo'],0,0,0,len(b),1,1,1,0,0,256,48,2,2,len(a)]
        (folder/'ui.u32').write_bytes(struct.pack('<17I',*ui))
        p=subprocess.run([str(APP/'host/render.exe'),str(case/'input400.u32'),str(case/'enhanced400.u32'),str(folder/'new.f32'),str(folder/'baseline.f32'),str(folder/'ui.u32'),str(folder/'frame.bgr')],capture_output=True,text=True)
        assert p.returncode==0 and 'GUARDS_PASS' in p.stdout
        Image.fromarray(np.fromfile(folder/'frame.bgr',np.uint8).reshape(480,800,3)[:,:,::-1]).save(folder/'HOST_PREVIEW_NOT_BOARD.png')
    write(out/'complete.json',dict(status='ALL6_HOST_LAYOUT_RENDERER_GUARDS_PASS_NOT_HARDWARE',hardware_access=False,sd_written=False))
    print('ACCURACY_HOST_UI_ALL6_PASS',flush=True)
if __name__=='__main__':main()
