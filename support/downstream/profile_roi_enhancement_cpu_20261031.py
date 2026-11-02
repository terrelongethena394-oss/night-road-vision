import time,numpy as np
from prove_student_fusion_20261031 import Engine
from pilot_car_roi_verify_20261031 import roi_pixels
def main():
    rng=np.random.default_rng(7);a=rng.integers(0,48,(240,400,3),np.uint8);sensor=rng.integers(0,48,(480,800,3),np.uint8);e=Engine()
    for name,fn in [('native_roi',lambda:roi_pixels(sensor,dict(x=20,y=120))),('current_enhancer',lambda:e.run(a))]:
        t=time.monotonic()
        for _ in range(4):fn()
        print(name,'seconds_each',(time.monotonic()-t)/4,flush=True)
if __name__=='__main__':main()
