"""AS7341 F1-F8/clear/NIR I2C driver, injected bus & monotonic clock.

No machine imports or GPIO activation on import. Based on AS7341 datasheet
DS000504 and the published SMUX F1-4/F5-8 routing tables. The integrated
white illumination channel is explicitly disabled. UV excitation is external
and must be physically interlocked by a separately verified driver.
"""
_LOW=(0x30,0x01,0x00,0x00,0x00,0x42,0x00,0x00,0x50,0x00,
      0x00,0x00,0x20,0x04,0x00,0x30,0x01,0x50,0x00,0x06)
_HIGH=(0x00,0x00,0x00,0x40,0x02,0x00,0x10,0x03,0x50,0x10,
       0x03,0x00,0x00,0x00,0x24,0x00,0x00,0x50,0x00,0x06)
CHANNELS=("f415","f445","f480","f515","f555","f590")
_REG_ENABLE=0x80
_REG_CFG6=0xAF
_REG_STATUS2=0xA3
_REG_CH0=0x95
_REG_ATIME=0x81
_REG_ASTEP=0xCA
_REG_GAIN=0xAA
_REG_CONFIG=0x70
_REG_LED=0x74
_REG_CFG0=0xA9


class SensorUnavailable(Exception):
    pass


class AS7341:
    def __init__(self, i2c, clock, address=0x39, atime=29, astep=599, gain=5):
        if not 0<=atime<=255 or not 0<=astep<=65534 or not 0<=gain<=10:
            raise ValueError("Invalid AS7341 integration settings")
        self.i2c=i2c
        self.clock=clock
        self.address=address
        self.atime=atime
        self.astep=astep
        self.gain=gain
        self.initialized=False

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address,register,bytes((value,)))

    def _read(self, register):
        data=self.i2c.readfrom_mem(self.address,register,1)
        if not data or len(data)!=1:
            raise SensorUnavailable("AS7341 I2C read failed")
        return data[0]

    def _setbank(self, lower):
        reg=self._read(_REG_CFG0)
        self._write(_REG_CFG0,(reg|0x10) if lower else (reg&~0x10))

    def initialize(self):
        if self.address not in self.i2c.scan():
            raise SensorUnavailable("AS7341 not detected")
        self._write(_REG_ENABLE,0x01)
        self.clock.sleep_ms(10)
        # Disable integrated onboard white LED (not the external 365nm UV).
        self._setbank(True)
        try:
            self._write(_REG_CONFIG,self._read(_REG_CONFIG)&~0x08)
            self._write(_REG_LED,self._read(_REG_LED)&~0x80)
        finally:
            self._setbank(False)
        self._write(_REG_ATIME,self.atime)
        self._write(_REG_ASTEP,self.astep&255)
        self._write(_REG_ASTEP+1,self.astep>>8)
        self._write(_REG_GAIN,self.gain)
        self.initialized=True

    def _group(self, mapping):
        self._write(_REG_ENABLE,0x01) # SP_EN = 0 before switching SMUX
        self._write(_REG_CFG6,(self._read(_REG_CFG6)&~0x18)|0x10)
        for index,value in enumerate(mapping):
            self._write(index,value)
        self._write(_REG_ENABLE,0x11)
        start=self.clock.ticks_ms()
        while self._read(_REG_ENABLE)&0x10:
            if self.clock.ticks_diff(self.clock.ticks_ms(),start)>300:
                raise SensorUnavailable("AS7341 SMUX timeout")
            self.clock.sleep_ms(2)
        self._write(_REG_ENABLE,0x03)
        start=self.clock.ticks_ms()
        # Datasheet: STATUS2 AVALID bit 6
        while not self._read(_REG_STATUS2)&0x40:
            if self.clock.ticks_diff(self.clock.ticks_ms(),start)>1200:
                raise SensorUnavailable("AS7341 integration timeout")
            self.clock.sleep_ms(5)
        data=self.i2c.readfrom_mem(self.address,_REG_CH0,12)
        if len(data)!=12:
            raise SensorUnavailable("AS7341 short ADC read")
        values=[data[2*i]|(data[2*i+1]<<8) for i in range(6)]
        self._write(_REG_ENABLE,0x01)
        return values

    def read_spectrum(self):
        if not self.initialized:
            raise SensorUnavailable("AS7341 is not initialized")
        try:
            low=self._group(_LOW)
            high=self._group(_HIGH)
            readings=low[:4]+high[:2]
            if any(v>=65535 for v in readings):
                raise SensorUnavailable("AS7341 saturated measurement")
            return dict(zip(CHANNELS,readings))
        finally:
            # Never leave spectral ADC or accessory LED energized.
            self._write(_REG_ENABLE,0x01)

    def shutdown(self):
        self._write(_REG_ENABLE,0)
        self.initialized=False
