"""Module E software tests: optics, robust acquisition, calibration, inference."""
import math
import tempfile
import unittest

from drivers.as7341 import AS7341, SensorUnavailable, CHANNELS
from services.optics import OpticalCycle, features, validate_spectrum
from services.calibration import baseline_from_runs,validate_calibration,CalibrationError
from services.edge_model import Forest,FEATURE_KEYS,LABELS


class FakeClock:
    def __init__(self):self.now=0
    def ticks_ms(self):return self.now
    def ticks_diff(self,now,before):return now-before
    def sleep_ms(self,ms):self.now+=ms


class FakeUV:
    def __init__(self):self.on=False;self.events=[]
    def set_enabled(self,value):
        self.on=value
        self.events.append(value)


class FakeSensor:
    def __init__(self,samples):
        self.samples=list(samples)
    def read_spectrum(self):
        if not self.samples:
            raise RuntimeError("No sample")
        value=self.samples.pop(0)
        if isinstance(value,Exception):raise value
        return value


def spectrum(value=12):
    return {key:value for key in CHANNELS}


class OpticsTests(unittest.TestCase):
    def test_subtraction_clamps_ambient(self):
        raw=features(spectrum(20),spectrum(10))
        self.assertEqual(raw["totalFluorescence"],0)
        self.assertEqual(raw["spectral"]["f415"],0)

    def test_clean_baseline_subtraction(self):
        raw=features(spectrum(5),spectrum(20),spectrum(4))
        self.assertEqual(raw["spectral"]["f445"],11)
        self.assertEqual(raw["totalFluorescence"],66)

    def test_invalid_and_saturation_values(self):
        for sample in (spectrum(65535),spectrum(-1),spectrum(float("nan"))):
            with self.assertRaises(ValueError):
                validate_spectrum(sample)

    def test_repeated_on_off_and_median(self):
        reads=[spectrum(x) for x in (2,3,100,10,11,1000)]
        uv=FakeUV()
        clock=FakeClock()
        result=OpticalCycle(FakeSensor(reads),uv,clock,repeats=3,settle_ms=10).capture()
        self.assertEqual(result["uvOff"]["f415"],3)
        self.assertEqual(result["uvOn"]["f415"],11)
        self.assertEqual(result["spectral"]["f415"],8)
        self.assertFalse(uv.on)
        self.assertEqual(clock.now,10)

    def test_uv_turns_off_after_sensor_failure(self):
        uv=FakeUV()
        sensor=FakeSensor([spectrum(),spectrum(),RuntimeError("broken")])
        with self.assertRaises(RuntimeError):
            OpticalCycle(sensor,uv,FakeClock(),repeats=2).capture()
        self.assertFalse(uv.on)
        self.assertEqual(uv.events[-1],False)

    def test_invalid_configuration_disallowed(self):
        with self.assertRaises(ValueError):
            OpticalCycle(None,None,None,repeats=0)

    def test_calibration_needs_real_repeated_consistency(self):
        runs=[{"spectral":spectrum(10),"source":"PHYSICAL_CLEAN_WATER","runId":"run"+str(i)} for i in range(5)]
        result=baseline_from_runs(runs,"cell-geometry-01")
        self.assertEqual(validate_calibration(result,"cell-geometry-01"),result)
        with self.assertRaises(CalibrationError):
            validate_calibration(result,"different-cell")

    def test_synthetic_calibration_rejected(self):
        runs=[{"spectral":spectrum(10),"source":"SIMULATED","runId":"run"+str(i)}
              for i in range(5)]
        with self.assertRaises(CalibrationError):
            baseline_from_runs(runs,"cell")

    def test_duplicate_clean_run_ids_rejected(self):
        runs=[{"spectral":spectrum(10),"source":"PHYSICAL_CLEAN_WATER","runId":"same"}
              for i in range(5)]
        with self.assertRaises(CalibrationError):
            baseline_from_runs(runs,"cell")

    def test_unstable_calibration_rejected(self):
        runs=[{"spectral":spectrum(x),"source":"PHYSICAL_CLEAN_WATER","runId":"run"+str(i)} for i,x in enumerate((1,1,1,1,100))]
        with self.assertRaises(CalibrationError):
            baseline_from_runs(runs,"cell")


class FakeI2C:
    def __init__(self,attached=True):
        self.attached=attached
        self.reg={0x80:0,0xA9:0,0xAF:0,0xA3:0x40}
        self.writes=[]
    def scan(self):
        return [0x39] if self.attached else []
    def writeto_mem(self,addr,reg,data):
        value=data[0]
        self.writes.append((reg,value))
        self.reg[reg]=value&~0x10 if reg==0x80 else value
    def readfrom_mem(self,addr,reg,n):
        if n==12 and reg==0x95:
            return b"".join(bytes((i,0)) for i in (10,20,30,40,50,60))
        return bytes((self.reg.get(reg,0),))


class SensorTests(unittest.TestCase):
    def test_sensor_missing_is_not_oil_detection(self):
        chip=AS7341(FakeI2C(attached=False),FakeClock())
        with self.assertRaises(SensorUnavailable):
            chip.initialize()

    def test_i2c_driver_read_and_safe_shutdown(self):
        bus=FakeI2C()
        chip=AS7341(bus,FakeClock())
        chip.initialize()
        values=chip.read_spectrum()
        self.assertEqual(set(values),set(CHANNELS))
        self.assertEqual(values["f590"],20)
        chip.shutdown()
        self.assertEqual(bus.reg[0x80],0)

    def test_invalid_gain_rejected(self):
        with self.assertRaises(ValueError):
            AS7341(FakeI2C(),FakeClock(),gain=20)


class ForestTests(unittest.TestCase):
    def make_model(self):
        leaf_a=[-1,[1,0,0],0,0]
        leaf_b=[-1,[0,1,0],0,0]
        tree=[[6,30.0,1,2],leaf_a,leaf_b]
        return {"schema":1,"version":"lab-demo-do-not-deploy",
                "features":list(FEATURE_KEYS),"classes":list(LABELS),
                "minConfidence":0.8,"trees":[tree]}

    def test_inference_consistent(self):
        forest=Forest(self.make_model())
        result=features(spectrum(5),spectrum(12))
        self.assertEqual(forest.predict(result)["classification"],"PETROLEUM")
        self.assertEqual(forest.predict(features(spectrum(3),spectrum(4)))["classification"],"NORMAL")

    def test_uncertain_model_abstains(self):
        model=self.make_model()
        model["trees"]=[[[-1,[1,1,0],0,0]]]
        result=Forest(model).predict(features(spectrum(3),spectrum(4)))
        self.assertEqual(result["classification"],"INCONCLUSIVE")

    def test_invalid_model_rejected(self):
        model=self.make_model()
        model["features"]=["wrong"]
        with self.assertRaises(ValueError):
            Forest(model)


if __name__=="__main__":
    unittest.main()
