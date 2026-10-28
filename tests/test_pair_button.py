"""D physical PAIR, explicit identity/transport dependency tests."""
import json
import tempfile
import unittest
from pathlib import Path

import main
from drivers.physical_pair_button import PairButton
from services.device_identity import load_identity, IdentityNotProvisioned


class Clock:
    def __init__(self):self.now=0
    def ticks_ms(self):return self.now
    def ticks_diff(self,a,b):return a-b
    def sleep_ms(self,v):self.now+=v


class Pin:
    def __init__(self,initial=1):self.v=initial
    def value(self):return self.v


class PairHardwareTests(unittest.TestCase):
    def test_press_after_stable_release(self):
        clock=Clock()
        pin=Pin()
        b=PairButton(pin,clock)
        self.assertFalse(b.poll())
        pin.v=0
        self.assertFalse(b.poll())
        clock.now=61
        self.assertTrue(b.poll())
        self.assertFalse(b.poll())
        pin.v=1
        b.poll()
        clock.now=122
        self.assertFalse(b.poll())
        pin.v=0
        b.poll()
        clock.now=183
        self.assertTrue(b.poll())

    def test_boot_held_button_cannot_pair_without_release(self):
        clock=Clock()
        pin=Pin(0)
        b=PairButton(pin,clock)
        clock.now=100
        self.assertFalse(b.poll())
        pin.v=1
        b.poll()
        clock.now=162
        self.assertFalse(b.poll())
        pin.v=0
        b.poll()
        clock.now=224
        self.assertTrue(b.poll())

    def test_bounce_does_not_pair(self):
        clock=Clock()
        pin=Pin(1)
        b=PairButton(pin,clock)
        for i in range(10):
            pin.v=i%2
            clock.now+=5
            self.assertFalse(b.poll())

    def test_identity_never_accepts_bad_key(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"id.json"
            p.write_text(json.dumps({"schema":1,"deviceId":"buoy_01","deviceKey":"short"}))
            with self.assertRaises(IdentityNotProvisioned):
                load_identity(str(p))
            p.write_text(json.dumps({"schema":1,"deviceId":"buoy_01","deviceKey":"x"*48}))
            self.assertEqual(load_identity(str(p))["deviceId"],"buoy_01")

    def test_identity_missing_is_not_cloud_ready(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(IdentityNotProvisioned):
                load_identity(str(Path(d)/"none.json"))

    def test_no_pairing_without_physical_source(self):
        class FakePair:
            pass
        with self.assertRaises(ValueError):
            main.serve_forever(clock=Clock(),max_ticks=1,
                               pairing_service=FakePair(),output=lambda _:None)

    def test_pairing_service_only_pollable_with_verified_input(self):
        class FakePair:
            def __init__(self):self.attempts=0;self.ticks=0
            def physically_pressed(self):self.attempts+=1
            def tick(self):self.ticks+=1
        class FakeInput:
            def __init__(self):self.pressed=False
            def poll(self):
                if self.pressed:return True
                self.pressed=True
                return False
        pair=FakePair()
        state=main.serve_forever(clock=Clock(),max_ticks=3,output=lambda _:None,
                                 pairing_service=pair,pair_input=FakeInput())
        self.assertEqual(pair.attempts,2)
        self.assertEqual(pair.ticks,3)
        self.assertEqual(state["state"],"RUNNING_OFFLINE")


if __name__=="__main__":
    unittest.main()
