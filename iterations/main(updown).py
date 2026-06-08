from machine import Pin, I2C
from time import sleep_ms, ticks_ms, ticks_diff

# -----------------------------
# MPU6050 settings
# -----------------------------
MPU_ADDR = 0x68

SCL_PIN = 22
SDA_PIN = 21
I2C_FREQ = 400000

PWR_MGMT_1 = 0x6B
ACCEL_ZOUT_H = 0x3F

# -----------------------------
# Motion detection settings
# -----------------------------
SAMPLE_DELAY_MS = 20       # 50 samples per second

FILTER_ALPHA = 0.85        # Higher = smoother, but more delay

UP_THRESHOLD = 900         # Increase if too sensitive
DOWN_THRESHOLD = -900      # Increase magnitude if too sensitive

MIN_TIME_BETWEEN_REPS = 400   # milliseconds, prevents double-counting

# -----------------------------
# I2C setup
# -----------------------------
i2c = I2C(
    0,
    scl=Pin(SCL_PIN),
    sda=Pin(SDA_PIN),
    freq=I2C_FREQ
)

# -----------------------------
# Helper functions
# -----------------------------
def read_raw_16(register):
    high = i2c.readfrom_mem(MPU_ADDR, register, 1)[0]
    low = i2c.readfrom_mem(MPU_ADDR, register + 1, 1)[0]

    value = (high << 8) | low

    if value > 32767:
        value -= 65536

    return value


def wake_mpu6050():
    i2c.writeto_mem(MPU_ADDR, PWR_MGMT_1, b'\x00')
    sleep_ms(100)


def check_connection():
    devices = i2c.scan()

    if MPU_ADDR not in devices:
        print("ERROR: MPU6050 not found")
        return False

    return True


# -----------------------------
# Main program
# -----------------------------
wake_mpu6050()

if not check_connection():
    while True:
        sleep_ms(1000)

# Starting values
z_filtered = read_raw_16(ACCEL_ZOUT_H)
z_previous = z_filtered

rep_count = 0
state = "WAITING_FOR_UP"
last_rep_time = ticks_ms()

print("READY")

while True:
    # Read vertical Z acceleration
    z_raw = read_raw_16(ACCEL_ZOUT_H)

    # Smooth the signal
    z_filtered = (FILTER_ALPHA * z_filtered) + ((1 - FILTER_ALPHA) * z_raw)

    # Motion value is the change in Z acceleration
    z_motion = z_filtered - z_previous
    z_previous = z_filtered

    current_time = ticks_ms()

    # Step 1: detect upward movement
    if state == "WAITING_FOR_UP":
        if z_motion > UP_THRESHOLD:
            state = "WAITING_FOR_DOWN"

    # Step 2: detect downward movement after upward movement
    elif state == "WAITING_FOR_DOWN":
        if z_motion < DOWN_THRESHOLD:
            if ticks_diff(current_time, last_rep_time) > MIN_TIME_BETWEEN_REPS:
                rep_count += 1
                last_rep_time = current_time
                print(rep_count)

            state = "WAITING_FOR_UP"

    sleep_ms(SAMPLE_DELAY_MS)