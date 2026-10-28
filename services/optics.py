"""UV-OFF / UV-ON spectral protocol and physical-calibration-ready features.

Never enables UV until injected verified control explicitly authorizes it.
Measurement results are NOT oil detections without a validated model.
"""
import math
from drivers.as7341 import CHANNELS


def _median(values):
    ordered=sorted(values)
    count=len(ordered)
    if count==0:
        raise ValueError("No readings")
    mid=count//2
    return ordered[mid] if count%2 else (ordered[mid-1]+ordered[mid])/2


def validate_spectrum(spectrum):
    if not isinstance(spectrum,dict) or set(spectrum)!=set(CHANNELS):
        raise ValueError("Expected exactly six AS7341 channels")
    result={}
    for channel in CHANNELS:
        value=spectrum[channel]
        if isinstance(value,bool) or not isinstance(value,(int,float)):
            raise ValueError("Invalid spectral value")
        if not math.isfinite(value) or value<0 or value>=65535:
            raise ValueError("Unsafe or saturated spectral value")
        result[channel]=float(value)
    return result


def features(uv_off, uv_on, baseline=None):
    """Clamp sensor dark-subtraction at zero, then subtract optional clean baseline."""
    off=validate_spectrum(uv_off)
    on=validate_spectrum(uv_on)
    bg={k:max(0.0,on[k]-off[k]) for k in CHANNELS}
    if baseline is not None:
        ref=validate_spectrum(baseline)
        corrected={k:max(0.0,bg[k]-ref[k]) for k in CHANNELS}
    else:
        corrected=bg
    total=sum(corrected.values())
    # Ratios feature-only; not part of strict API measurement spectral schema.
    ratio_590_445=corrected["f590"]/(corrected["f445"]+1.0)
    slope=(corrected["f590"]-corrected["f415"])/175.0
    return {"spectral":corrected,"totalFluorescence":total,
            "ratio590to445":ratio_590_445,"slope415to590":slope}


class OpticalCycle:
    """Sensor read_spectrum, UV set_enabled(True/False), clock sleep_ms.

    The external UV enable control MUST be physically verified, interlocked,
    and fail-OFF. No direct GPIO handling is provided here.
    """
    def __init__(self,sensor,uv,clock,repeats=3,settle_ms=3000):
        if type(repeats) is not int or not 1<=repeats<=20:
            raise ValueError("Invalid repeat count")
        if type(settle_ms) is not int or not 0<=settle_ms<=120000:
            raise ValueError("Invalid settle duration")
        self.sensor=sensor
        self.uv=uv
        self.clock=clock
        self.repeats=repeats
        self.settle_ms=settle_ms

    def capture(self,baseline=None):
        self.uv.set_enabled(False)
        try:
            off=[validate_spectrum(self.sensor.read_spectrum()) for _ in range(self.repeats)]
            uv_on=[]
            self.uv.set_enabled(True)
            self.clock.sleep_ms(self.settle_ms)
            for _ in range(self.repeats):
                uv_on.append(validate_spectrum(self.sensor.read_spectrum()))
        finally:
            self.uv.set_enabled(False)
        background={k:_median([s[k] for s in off]) for k in CHANNELS}
        excited={k:_median([s[k] for s in uv_on]) for k in CHANNELS}
        answer=features(background,excited,baseline)
        answer["uvOff"]=background
        answer["uvOn"]=excited
        answer["repeatCount"]=self.repeats
        return answer
