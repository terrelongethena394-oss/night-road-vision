"""New, prospectively tested low-light false-positive reduction hypothesis."""
from road_viewadapt_common import BASE,DATA,WEIGHTS,read,write,sha,metrics,NAMES
from pathlib import Path
ROOT=BASE/'road_brightness_route_20261030_r1'
ADAPT=BASE/'road_viewadapt_20261030_r1'
SEED=2026103097
GATE_MEAN=48.
GAINS=[1.75,1.1]

def gates(old,new):
 a=old['all']['classes'];b=new['all']['classes'];tp=lambda z:sum(z[k]['tp'] for k in ['truck','bus']);fp=lambda z:sum(z[k]['fp'] for k in ['truck','bus'])
 return dict(car_ap_noninferior=b['car']['ap50']>=a['car']['ap50']-.005,car_precision_noninferior=b['car']['precision']>=a['car']['precision']-.005,car_recall_noninferior=b['car']['recall']>=a['car']['recall']-.005,fourclass_map_noninferior=new['all']['mAP50']>=old['all']['mAP50']-.002,truck_bus_tp_retained90=tp(b)>=.9*tp(a),truck_bus_fp_reduced25=fp(b)<=.75*fp(a))

