"""Independent NumPy audit of real ARM input tensors and all33 signed logits."""
from pathlib import Path
import json,sys,hashlib,subprocess
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
SOURCE=Path('C:/Users/曹/Documents/ChatGPT/FPGA创新设计大赛/starter/downstream')
MODEL=Path('E:/FPGA_Enhance_Work/real_digit_training_20261025/cnn_candidate/real_digit_cnn.pth')
def pooled(image,x,y,size):
    a=image[y:y+size,x:x+size,:3].astype(np.uint32)
    g=(77*a[:,:,0]+150*a[:,:,1]+29*a[:,:,2]+128)>>8;c=size//28
    return ((g.reshape(28,c,28,c).sum((1,3))+c*c//2)//(c*c)).astype(np.uint8)
def main():
    folder=Path(sys.argv[1]);subprocess.run([sys.executable,str(HERE/'validate_multinex_camera.py'),str(folder)],check=True,capture_output=True)
    model=MODEL;contract=1
    if (HERE/'classifier_frozen.json').exists():
        freeze=json.loads((HERE/'classifier_frozen.json').read_text());model=HERE/'classifier.pth' if (HERE/'classifier.pth').exists() else Path(freeze['model']);contract=2
        assert hashlib.sha256(model.read_bytes()).hexdigest()==freeze['sha256']
    else:assert hashlib.sha256(model.read_bytes()).hexdigest()=='07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493'
    t=[int(v,0) for v in (folder/'digit_telemetry.txt').read_text().split()]
    m=[int(v,0) for v in (folder/'mailbox.txt').read_text().split()]
    assert len(t)==15 and t[11:14]==[0x04e00000,0x04e01000,contract] and t[14]==m[5]
    x,y,size=t[8:11];assert 1<=x<400-size and 1<=y<240-size and 28<=size<=224 and size%28==0
    images=[np.fromfile(folder/n,np.uint8).reshape(240,400,4) for n in ('input32.bin','output32.bin','protected32.bin')]
    expected_gray=np.stack([pooled(v,x,y,size) for v in images])
    if contract==2:
        sys.path.insert(0,str(SOURCE));from recognition_upgrade_common import normalize_np
        expected_gray=normalize_np(expected_gray)
    actual_gray=np.fromfile(folder/'digit_gray.bin',np.uint8).reshape(3,28,28)
    assert np.array_equal(actual_gray,expected_gray),'Preprocessing differs'
    sys.path.insert(0,str(SOURCE));from train_real_digit_cnn import IntegerCNN
    q=IntegerCNN(torch.load(model,weights_only=True,map_location='cpu'))
    predictions,expected=q.infer(expected_gray)
    scores=np.fromfile(folder/'digit_scores.i64',dtype='<i8').reshape(3,11)
    assert np.array_equal(scores,expected),'ARM signed64 logits differ'
    assert t[:3]==predictions.tolist() and np.array_equal(scores.argmax(1),predictions)
    glyphs=[[14,17,19,21,25,17,14],[4,12,4,4,4,4,14],[14,17,1,2,4,8,31],
        [30,1,1,14,1,1,30],[2,6,10,18,31,2,2],[31,16,16,30,1,1,30],
        [14,16,16,30,17,17,14],[31,1,2,4,8,8,8],[14,17,17,14,17,17,14],
        [14,17,17,15,1,1,14],[0,0,0,31,0,0,0]]
    lcd=np.fromfile(folder/'display.bgr24',np.uint8).reshape(480,800,3)[:,:,::-1]
    for i,label in enumerate(predictions):
        bits=np.array([[(row>>(4-x))&1 for x in range(5)] for row in glyphs[int(label)]],np.uint8)
        want=np.repeat(np.repeat(bits,4,axis=0),4,axis=1)[:,:,None]*np.full((1,1,3),255,np.uint8)
        x0=45+i*260+90
        assert np.array_equal(lcd[388:416,x0:x0+20],want),'Displayed digit does not match actual classifier'
    reuse=np.array_equal(actual_gray[2],actual_gray[0]) or np.array_equal(actual_gray[2],actual_gray[1])
    assert t[7]==(2 if reuse else 3)
    result=dict(status='ACTUAL_ARM_CLASSIFIER_ALL_LOGITS_EXACT',views=['RAW','NET','AUTO'],
        predictions=predictions.tolist(),gray_bytes=2352,gray_exact=True,logits=33,logits_exact=True,display_digits_exact=True,
        roi=dict(x=x,y=y,size=size),physical_cnn_evaluations=t[7],same_tensor_reused=bool(reuse),
        raw_recognition_seconds=(t[3]+(t[4]<<32))/m[8],other_recognition_seconds=(t[5]+(t[6]<<32))/m[8],
        sequence=t[14],model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),input_contract=contract,
        note='One given single-digit ROI. Enhancement in PL, same integer CNN reused on ARM. No truth or expected label sent to device. Numeric equality does not prove correct classification, detection, plate OCR, or enhancement benefit.')
    (folder/'digit_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
