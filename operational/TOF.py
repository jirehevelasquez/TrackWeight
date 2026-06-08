from time import sleep_ms, ticks_ms, ticks_diff


class VL53L0X:
    ADDRESS = 0x29

    SYSRANGE_START = 0x00
    SYSTEM_SEQUENCE_CONFIG = 0x01
    SYSTEM_INTERRUPT_CONFIG_GPIO = 0x0A
    SYSTEM_INTERRUPT_CLEAR = 0x0B
    RESULT_INTERRUPT_STATUS = 0x13
    RESULT_RANGE_STATUS = 0x14
    RESULT_RANGE_MM = 0x1E

    I2C_SLAVE_DEVICE_ADDRESS = 0x8A

    VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV = 0x89
    MSRC_CONFIG_CONTROL = 0x60
    FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT = 0x44
    SYSTEM_RANGE_CONFIG = 0x09

    def __init__(self, i2c, address=ADDRESS, timeout_ms=1000):
        self.i2c = i2c
        self.address = address
        self.timeout_ms = timeout_ms
        self.stop_variable = 0
        self.init_sensor()

    def write8(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value & 0xFF]))

    def write16(self, reg, value):
        self.i2c.writeto_mem(
            self.address,
            reg,
            bytes([(value >> 8) & 0xFF, value & 0xFF])
        )

    def write32(self, reg, value):
        self.i2c.writeto_mem(
            self.address,
            reg,
            bytes([
                (value >> 24) & 0xFF,
                (value >> 16) & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF
            ])
        )

    def read8(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def read16(self, reg):
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        return (data[0] << 8) | data[1]

    def timeout_expired(self, start):
        return ticks_diff(ticks_ms(), start) > self.timeout_ms

    def check_model_id(self):
        model_id = self.read8(0xC0)
        module_type = self.read8(0xC1)
        revision = self.read8(0xC2)

        if model_id != 0xEE:
            raise RuntimeError("VL53L0X model ID failed")

        return model_id, module_type, revision

    def set_signal_rate_limit(self, limit_mcps):
        if limit_mcps < 0 or limit_mcps > 511.99:
            return False

        value = int(limit_mcps * (1 << 7))
        self.write16(self.FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT, value)
        return True

    def init_sensor(self):
        sleep_ms(100)

        self.check_model_id()

        # Set 2.8V I/O mode.
        self.write8(
            self.VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV,
            self.read8(self.VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV) | 0x01
        )

        # Basic private init sequence used by common VL53L0X drivers.
        self.write8(0x88, 0x00)
        self.write8(0x80, 0x01)
        self.write8(0xFF, 0x01)
        self.write8(0x00, 0x00)

        self.stop_variable = self.read8(0x91)

        self.write8(0x00, 0x01)
        self.write8(0xFF, 0x00)
        self.write8(0x80, 0x00)

        # Disable MSRC and pre-range limit checks.
        self.write8(
            self.MSRC_CONFIG_CONTROL,
            self.read8(self.MSRC_CONFIG_CONTROL) | 0x12
        )

        # Set signal rate limit to 0.25 MCPS.
        self.set_signal_rate_limit(0.25)

        # Enable all sequence steps first.
        self.write8(self.SYSTEM_SEQUENCE_CONFIG, 0xFF)

        # SPAD setup sequence.
        self.write8(0x80, 0x01)
        self.write8(0xFF, 0x01)
        self.write8(0x00, 0x00)
        self.write8(0xFF, 0x06)
        self.write8(0x83, self.read8(0x83) | 0x04)
        self.write8(0xFF, 0x07)
        self.write8(0x81, 0x01)
        self.write8(0x80, 0x01)
        self.write8(0x94, 0x6B)
        self.write8(0x83, 0x00)

        start = ticks_ms()
        while self.read8(0x83) == 0x00:
            if self.timeout_expired(start):
                raise RuntimeError("SPAD info timeout")
            sleep_ms(1)

        self.write8(0x83, 0x01)
        tmp = self.read8(0x92)

        spad_count = tmp & 0x7F
        spad_type_is_aperture = (tmp >> 7) & 0x01

        self.write8(0x81, 0x00)
        self.write8(0xFF, 0x06)
        self.write8(0x83, self.read8(0x83) & ~0x04)
        self.write8(0xFF, 0x01)
        self.write8(0x00, 0x01)
        self.write8(0xFF, 0x00)
        self.write8(0x80, 0x00)

        # Reference SPAD map setup.
        ref_spad_map = bytearray(self.i2c.readfrom_mem(self.address, 0xB0, 6))

        first_spad_to_enable = 12 if spad_type_is_aperture else 0
        spads_enabled = 0

        for i in range(48):
            if i < first_spad_to_enable or spads_enabled == spad_count:
                ref_spad_map[i // 8] &= ~(1 << (i % 8))
            elif ref_spad_map[i // 8] & (1 << (i % 8)):
                spads_enabled += 1

        self.i2c.writeto_mem(self.address, 0xB0, ref_spad_map)

        # Default tuning settings.
        self.load_tuning_settings()

        # Interrupt config: new sample ready.
        self.write8(self.SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04)
        self.write8(0x84, self.read8(0x84) & ~0x10)
        self.write8(self.SYSTEM_INTERRUPT_CLEAR, 0x01)

        # Run required calibrations.
        self.write8(self.SYSTEM_SEQUENCE_CONFIG, 0x01)
        self.perform_single_ref_calibration(0x40)

        self.write8(self.SYSTEM_SEQUENCE_CONFIG, 0x02)
        self.perform_single_ref_calibration(0x00)

        # Put sequence config back to useful default.
        self.write8(self.SYSTEM_SEQUENCE_CONFIG, 0xE8)

    def load_tuning_settings(self):
        # ST default tuning sequence commonly used by VL53L0X ports.
        settings = [
            (0xFF, 0x01), (0x00, 0x00),
            (0xFF, 0x00), (0x09, 0x00), (0x10, 0x00), (0x11, 0x00),
            (0x24, 0x01), (0x25, 0xFF), (0x75, 0x00),
            (0xFF, 0x01), (0x4E, 0x2C), (0x48, 0x00), (0x30, 0x20),
            (0xFF, 0x00), (0x30, 0x09), (0x54, 0x00), (0x31, 0x04),
            (0x32, 0x03), (0x40, 0x83), (0x46, 0x25), (0x60, 0x00),
            (0x27, 0x00), (0x50, 0x06), (0x51, 0x00), (0x52, 0x96),
            (0x56, 0x08), (0x57, 0x30), (0x61, 0x00), (0x62, 0x00),
            (0x64, 0x00), (0x65, 0x00), (0x66, 0xA0),
            (0xFF, 0x01), (0x22, 0x32), (0x47, 0x14), (0x49, 0xFF),
            (0x4A, 0x00),
            (0xFF, 0x00), (0x7A, 0x0A), (0x7B, 0x00), (0x78, 0x21),
            (0xFF, 0x01), (0x23, 0x34), (0x42, 0x00), (0x44, 0xFF),
            (0x45, 0x26), (0x46, 0x05), (0x40, 0x40), (0x0E, 0x06),
            (0x20, 0x1A), (0x43, 0x40),
            (0xFF, 0x00), (0x34, 0x03), (0x35, 0x44),
            (0xFF, 0x01), (0x31, 0x04), (0x4B, 0x09), (0x4C, 0x05),
            (0x4D, 0x04),
            (0xFF, 0x00), (0x44, 0x00), (0x45, 0x20), (0x47, 0x08),
            (0x48, 0x28), (0x67, 0x00), (0x70, 0x04), (0x71, 0x01),
            (0x72, 0xFE), (0x76, 0x00), (0x77, 0x00),
            (0xFF, 0x01), (0x0D, 0x01),
            (0xFF, 0x00), (0x80, 0x01), (0x01, 0xF8),
            (0xFF, 0x01), (0x8E, 0x01), (0x00, 0x01),
            (0xFF, 0x00), (0x80, 0x00),
        ]

        for reg, val in settings:
            self.write8(reg, val)

    def perform_single_ref_calibration(self, vhv_init_byte):
        self.write8(self.SYSRANGE_START, 0x01 | vhv_init_byte)

        start = ticks_ms()
        while (self.read8(self.RESULT_INTERRUPT_STATUS) & 0x07) == 0:
            if self.timeout_expired(start):
                raise RuntimeError("Calibration timeout")
            sleep_ms(1)

        self.write8(self.SYSTEM_INTERRUPT_CLEAR, 0x01)
        self.write8(self.SYSRANGE_START, 0x00)

    def start_continuous(self, period_ms=0):
        # Restore stop variable.
        self.write8(0x80, 0x01)
        self.write8(0xFF, 0x01)
        self.write8(0x00, 0x00)
        self.write8(0x91, self.stop_variable)
        self.write8(0x00, 0x01)
        self.write8(0xFF, 0x00)
        self.write8(0x80, 0x00)

        if period_ms != 0:
            # Timed continuous mode.
            self.write32(0x04, period_ms)
            self.write8(self.SYSRANGE_START, 0x04)
        else:
            # Back-to-back continuous mode.
            self.write8(self.SYSRANGE_START, 0x02)

    def stop_continuous(self):
        self.write8(self.SYSRANGE_START, 0x01)
        self.write8(0xFF, 0x01)
        self.write8(0x00, 0x00)
        self.write8(0x91, 0x00)
        self.write8(0x00, 0x01)
        self.write8(0xFF, 0x00)

    def read_continuous_mm(self):
        start = ticks_ms()

        while (self.read8(self.RESULT_INTERRUPT_STATUS) & 0x07) == 0:
            if self.timeout_expired(start):
                return -1
            sleep_ms(1)

        distance = self.read16(self.RESULT_RANGE_MM)
        self.write8(self.SYSTEM_INTERRUPT_CLEAR, 0x01)

        return distance

    def read(self):
        return self.read_continuous_mm()