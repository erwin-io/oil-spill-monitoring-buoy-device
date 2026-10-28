"""Clean-water calibration record and repeatability checks.

Store only data from physically measured final optical assembly. No built-in
synthetic baseline may be promoted to a production calibration.
"""
import json
from services.optics import validate_spectrum
from drivers.as7341 import CHANNELS


class CalibrationError(ValueError):
    pass


def baseline_from_runs(runs,geometry_id,min_runs=5,max_cv=0.12):
    if not isinstance(geometry_id,str) or not 1<=len(geometry_id)<=64:
        raise CalibrationError("Geometry ID required")
    if len(runs)<min_runs:
        raise CalibrationError("Insufficient independent clean-water runs")
    if any(not isinstance(x,dict) or x.get("source")!="PHYSICAL_CLEAN_WATER"
           or not isinstance(x.get("runId"),str) or not x["runId"]
           for x in runs):
        raise CalibrationError("Physical sample evidence is required")
    if len({x["runId"] for x in runs})!=len(runs):
        raise CalibrationError("Independent run IDs must not be reused")
    spectra=[validate_spectrum(x["spectral"]) for x in runs]
    mean={k:sum(r[k] for r in spectra)/len(runs) for k in CHANNELS}
    cv={}
    for k in CHANNELS:
        variance=sum((r[k]-mean[k])**2 for r in spectra)/len(runs)
        cv[k]=(variance**0.5)/(mean[k] if mean[k]>=1 else 1)
    if any(value>max_cv for value in cv.values()):
        raise CalibrationError("Repeatability exceeds acceptance threshold")
    return {"schema":1,"geometryId":geometry_id,"runs":len(runs),
            "baseline":mean,"coefficientOfVariation":cv,
            "source":"PHYSICAL_CLEAN_WATER_ONLY"}


def validate_calibration(record,geometry_id):
    if not isinstance(record,dict) or record.get("schema")!=1 or record.get("geometryId")!=geometry_id or record.get("source")!="PHYSICAL_CLEAN_WATER_ONLY":
        raise CalibrationError("Missing/mismatched physical calibration")
    validate_spectrum(record.get("baseline"))
    if type(record.get("runs"))!=int or record["runs"]<5:
        raise CalibrationError("Calibration lacks repeated runs")
    cv=record.get("coefficientOfVariation")
    if not isinstance(cv,dict) or set(cv)!=set(CHANNELS) or any(
        type(value) not in (float,int) or not 0<=value<=0.12 for value in cv.values()):
        raise CalibrationError("Calibration repeatability not established")
    return record


def load_calibration(path,geometry_id):
    with open(path,"r") as f:
        record=json.load(f)
    return validate_calibration(record,geometry_id)
