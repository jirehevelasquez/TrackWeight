# main.py
# Track Weight test file
# WiFi disabled
# BOOT button starts one workout session
# TOF calculates selected weight
# IMU counts reps

from machine import Pin, I2C
import time

from weight_map import WeightMap
from TOF import VL53L0X
from IMU import MPU6050


# -----------------------------
# I2C SETTINGS
# -----------------------------

I2C_ID = 0
I2C_SDA_PIN = 21
I2C_SCL_PIN = 22
I2C_FREQ = 400000


# -----------------------------
# BUTTON SETTINGS
# -----------------------------

# ESP32 BOOT button is usually GPIO 0.
# Pressed = 0
# Not pressed = 1
BOOT_BUTTON_PIN = 0


# -----------------------------
# WEIGHT STACK SETTINGS
# -----------------------------
# CHANGE THESE VALUES AFTER TESTING

# TOF reading when pin is at the lightest weight.
HOME_DISTANCE_MM = 120

# Distance between each pin hole / plate thickness.
PLATE_THICKNESS_MM = 25

# Lightest selectable weight.
START_WEIGHT_LBS = 10

# Amount added when pin moves down one hole.
WEIGHT_STEP_LBS = 10

# If there are 10 selectable holes, max slot is 9 because slot 0 is the first hole.
MAX_SLOTS = 9

# Use this if TOF reading gets larger as pin moves down.
DIRECTION = "down_increases_distance"

# Use this instead if TOF reading gets smaller as pin moves down.
# DIRECTION = "down_decreases_distance"


# -----------------------------
# TEST SETTINGS
# -----------------------------

TOF_SAMPLES = 10

# The session ends this long after the last detected rep.
SESSION_TIMEOUT_MS = 15000

# Prevents one movement from being counted multiple times.
MIN_REP_TIME_MS = 600

# Raw IMU threshold.
# You may need to tune this.
# Larger number = harder to count a rep.
# Smaller number = easier to count a rep.
REP_DELTA_THRESHOLD = 2500


# -----------------------------
# GLOBAL OBJECTS
# -----------------------------

boot_button = Pin(BOOT_BUTTON_PIN, Pin.IN, Pin.PULL_UP)

i2c = None
tof = None
imu = None

weight_map = WeightMap(
    home_distance_mm=HOME_DISTANCE_MM,
    plate_thickness_mm=PLATE_THICKNESS_MM,
    start_weight_lbs=START_WEIGHT_LBS,
    weight_step_lbs=WEIGHT_STEP_LBS,
    max_slots=MAX_SLOTS,
    direction=DIRECTION
)


# -----------------------------
# SENSOR SETUP
# -----------------------------

def init_sensors():
    global i2c, tof, imu

    print("Starting I2C...")
    i2c = I2C(
        I2C_ID,
        sda=Pin(I2C_SDA_PIN),
        scl=Pin(I2C_SCL_PIN),
        freq=I2C_FREQ
    )

    devices = i2c.scan()
    print("I2C devices found:", devices)

    print("Starting TOF sensor...")
    tof = VL53L0X(i2c)
    tof.start_continuous()
    time.sleep(0.1)

    print("Starting IMU...")
    imu = MPU6050(i2c)

    print("Sensors ready")


# -----------------------------
# BUTTON FUNCTIONS
# -----------------------------

def boot_button_pressed():
    return boot_button.value() == 0


def wait_for_button_press():
    print("")
    print("Waiting for BOOT button press...")

    while not boot_button_pressed():
        time.sleep(0.05)

    # Debounce delay
    time.sleep(0.25)

    while boot_button_pressed():
        time.sleep(0.05)

    print("BOOT button pressed")
    print("Starting test session")


# -----------------------------
# TOF FUNCTIONS
# -----------------------------

def read_tof_mm():
    distance = tof.read()

    # Your TOF driver returns -1 if it times out.
    if distance is None or distance <= 0:
        return None

    return distance


def average_tof_reading(samples=TOF_SAMPLES):
    total = 0
    valid_samples = 0

    for i in range(samples):
        distance = read_tof_mm()

        if distance is not None:
            total += distance
            valid_samples += 1
            print("TOF sample", i + 1, ":", distance, "mm")
        else:
            print("TOF sample", i + 1, ": invalid")

        time.sleep(0.05)

    if valid_samples == 0:
        return None

    return total / valid_samples


def detect_selected_weight():
    print("")
    print("Reading selected weight...")

    distance_mm = average_tof_reading()

    if distance_mm is None:
        print("Could not get valid TOF reading")
        return None

    weight_lbs, error_mm, matched_distance, slot = weight_map.get_weight_with_error(distance_mm)

    print("")
    print("Average TOF distance:", distance_mm, "mm")
    print("Matched slot:", slot)
    print("Matched slot distance:", matched_distance, "mm")
    print("Distance error:", error_mm, "mm")
    print("Selected weight:", weight_lbs, "lbs")

    return weight_lbs


# -----------------------------
# IMU REP COUNTER
# -----------------------------

def get_imu_baseline(samples=50):
    print("")
    print("Calibrating IMU baseline. Keep the machine still...")

    total = 0

    for i in range(samples):
        z = imu.read_z_filtered()
        total += z
        time.sleep(0.02)

    baseline = total / samples

    print("IMU baseline:", baseline)

    return baseline


class RepCounter:
    def __init__(self, baseline, delta_threshold, min_rep_time_ms):
        self.baseline = baseline
        self.delta_threshold = delta_threshold
        self.min_rep_time_ms = min_rep_time_ms

        self.state = "waiting_for_movement"
        self.reps = 0
        self.last_rep_time = 0

    def update(self, z_value):
        now = time.ticks_ms()
        delta = z_value - self.baseline

        if self.state == "waiting_for_movement":
            if abs(delta) > self.delta_threshold:
                self.state = "waiting_for_return"

        elif self.state == "waiting_for_return":
            if abs(delta) < self.delta_threshold / 2:
                time_since_last_rep = time.ticks_diff(now, self.last_rep_time)

                if time_since_last_rep > self.min_rep_time_ms:
                    self.reps += 1
                    self.last_rep_time = now
                    print("Rep counted. Total reps:", self.reps)

                self.state = "waiting_for_movement"

        return self.reps


def count_reps():
    baseline = get_imu_baseline()

    rep_counter = RepCounter(
        baseline=baseline,
        delta_threshold=REP_DELTA_THRESHOLD,
        min_rep_time_ms=MIN_REP_TIME_MS
    )

    print("")
    print("Starting rep detection...")
    print("Move the weight stack now.")
    print("Current REP_DELTA_THRESHOLD:", REP_DELTA_THRESHOLD)

    last_motion_time = time.ticks_ms()
    last_reps = 0

    while True:
        z = imu.read_z_filtered()
        reps = rep_counter.update(z)

        if reps != last_reps:
            last_reps = reps
            last_motion_time = time.ticks_ms()

        if reps > 0:
            inactive_time = time.ticks_diff(time.ticks_ms(), last_motion_time)

            if inactive_time > SESSION_TIMEOUT_MS:
                print("No new reps detected. Ending session.")
                break

        time.sleep(0.03)

    return rep_counter.reps


# -----------------------------
# MAIN PROGRAM
# -----------------------------

def main():
    print("")
    print("Track Weight WiFi-disabled test")
    print("-------------------------------")

    init_sensors()

    print("")
    print("WiFi is disabled for this test.")
    print("The ESP32 will only print results in Thonny.")

    while True:
        wait_for_button_press()

        selected_weight = detect_selected_weight()

        if selected_weight is None:
            print("Skipping session because weight could not be detected")
            continue

        reps = count_reps()

        print("")
        print("Workout test complete")
        print("---------------------")
        print("Weight:", selected_weight, "lbs")
        print("Reps:", reps)
        print("Data was NOT sent over WiFi.")
        print("Ready for next BOOT button press.")

        time.sleep(1)


main()