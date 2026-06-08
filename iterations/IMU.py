from time import sleep_ms


class MPU6050:
    ADDRESS = 0x68

    PWR_MGMT_1 = 0x6B

    ACCEL_XOUT_H = 0x3B
    ACCEL_YOUT_H = 0x3D
    ACCEL_ZOUT_H = 0x3F

    TEMP_OUT_H = 0x41

    GYRO_XOUT_H = 0x43
    GYRO_YOUT_H = 0x45
    GYRO_ZOUT_H = 0x47

    def __init__(self, i2c, address=ADDRESS):
        self.i2c = i2c
        self.address = address

        self.ax_f = 0
        self.ay_f = 0
        self.az_f = 0

        self.gx_f = 0
        self.gy_f = 0
        self.gz_f = 0

        self.wake()
        self.initialize_filters()

    def wake(self):
        self.i2c.writeto_mem(self.address, self.PWR_MGMT_1, b'\x00')
        sleep_ms(100)

    def read_raw_16(self, register):
        high = self.i2c.readfrom_mem(self.address, register, 1)[0]
        low = self.i2c.readfrom_mem(self.address, register + 1, 1)[0]

        value = (high << 8) | low

        if value > 32767:
            value -= 65536

        return value

    def initialize_filters(self):
        ax, ay, az = self.read_accel_raw()
        gx, gy, gz = self.read_gyro_raw()

        self.ax_f = ax
        self.ay_f = ay
        self.az_f = az

        self.gx_f = gx
        self.gy_f = gy
        self.gz_f = gz

    def low_pass(self, previous, current, alpha):
        return (alpha * previous) + ((1 - alpha) * current)

    def read_accel_raw(self):
        ax = self.read_raw_16(self.ACCEL_XOUT_H)
        ay = self.read_raw_16(self.ACCEL_YOUT_H)
        az = self.read_raw_16(self.ACCEL_ZOUT_H)

        return ax, ay, az

    def read_gyro_raw(self):
        gx = self.read_raw_16(self.GYRO_XOUT_H)
        gy = self.read_raw_16(self.GYRO_YOUT_H)
        gz = self.read_raw_16(self.GYRO_ZOUT_H)

        return gx, gy, gz

    def read_all_raw(self):
        ax, ay, az = self.read_accel_raw()
        gx, gy, gz = self.read_gyro_raw()

        return ax, ay, az, gx, gy, gz

    def read_all_filtered(self, accel_alpha=0.85, gyro_alpha=0.75):
        ax, ay, az, gx, gy, gz = self.read_all_raw()

        self.ax_f = self.low_pass(self.ax_f, ax, accel_alpha)
        self.ay_f = self.low_pass(self.ay_f, ay, accel_alpha)
        self.az_f = self.low_pass(self.az_f, az, accel_alpha)

        self.gx_f = self.low_pass(self.gx_f, gx, gyro_alpha)
        self.gy_f = self.low_pass(self.gy_f, gy, gyro_alpha)
        self.gz_f = self.low_pass(self.gz_f, gz, gyro_alpha)

        return (
            int(self.ax_f),
            int(self.ay_f),
            int(self.az_f),
            int(self.gx_f),
            int(self.gy_f),
            int(self.gz_f)
        )

    def read_z_raw(self):
        return self.read_raw_16(self.ACCEL_ZOUT_H)

    def read_z_filtered(self, alpha=0.85):
        z_raw = self.read_z_raw()
        self.az_f = self.low_pass(self.az_f, z_raw, alpha)
        return int(self.az_f)

    def check_connection(self):
        devices = self.i2c.scan()
        return self.address in devices