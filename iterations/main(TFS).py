from machine import Pin, I2C
from time import sleep_ms
from TOF import VL53L0X

SCL_PIN = 22
SDA_PIN = 21

i2c = I2C(
    0,
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN),
    freq=100000
)

print("I2C:", i2c.scan())

tof = VL53L0X(i2c)
tof.start_continuous()

print("READY")

while True:
    distance_mm = tof.read()

    if distance_mm >= 0:
        print(distance_mm)
    else:
        print("TIMEOUT")

    sleep_ms(100)
