from road_roi_spatial_common import ROOT,CHECKPOINTS,FLOORS,make_model
import evaluate_road_roi_verifier as run
run.ROOT=ROOT;run.CHECKPOINTS=CHECKPOINTS;run.FLOORS=FLOORS;run.make_model=make_model
if __name__=='__main__':run.main()
