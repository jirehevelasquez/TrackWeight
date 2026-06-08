# main.py
# Track Weight full code
# BOOT button starts session
# TOF calculates selected weight
# IMU counts reps
# WiFi sends selected workout data to Supabase

from machine import Pin, I2C
import time
import network
import urequests

from weight_map import WeightMap
from TOF import VL53L0X
from IMU import MPU6050


# -----------------------------
# WIFI SETTINGS
# -----------------------------
# Use the laptop hotspot values that worked in your WiFi test.

WIFI_NAME = "MONGOTHEGINGERB 1812"
WIFI_PASSWORD = "add here"


# -----------------------------
# SUPABASE SETTINGS
# -----------------------------
# Replace SUPABASE_KEY with your real Supabase anon public key.

SUPABASE_URL = "https://rwreglitqcnlfwaugngf.supabase.co/rest/v1/workout_events"
SUPABASE_KEY = "add here accordinly"

# Identification values from your friend's code
MACHINE_NAME = "benchpress"
USER_SLOT = 1

# This is printed locally for debugging, but it is NOT sent to Supabase.
DEVICE_ID = "track_weight_esp32_001"


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

BOOT_BUTTON_PIN = 0


# -----------------------------
# WEIGHT STACK SETTINGS
# -----------------------------
# Change these after calibration.

HOME_DISTANCE_MM = 120
PLATE_THICKNESS_MM = 25
START_WEIGHT_LBS = 10
WEIGHT_STEP_LBS = 10
MAX_SLOTS = 9

DIRECTION = "down_increases_distance"
# DIRECTION = "down_decreases_distance"


# -----------------------------
# TEST / REP SETTINGS
# -----------------------------

TOF_SAMPLES = 10

SESSION_TIMEOUT_MS = 15000
MIN_REP_TIME_MS = 600

# This worked during your previous rep test.
REP_DELTA_THRESHOLD = 2500


# -----------------------------
# GLOBAL OBJECTS
# -----------------------------

boot_button = Pin(BOOT_BUTTON_PIN, Pin.IN, Pin.PULL_UP)

i2c = None
tof = None
imu = None
wifi_ready = False

weight_map = WeightMap(
    home_distance_mm=HOME_DISTANCE_MM,
    plate_thickness_mm=PLATE_THICKNESS_MM,
    start_weight_lbs=START_WEIGHT_LBS,
    weight_step_lbs=WEIGHT_STEP_LBS,
    max_slots=MAX_SLOTS,
    direction=DIRECTION
)


# -----------------------------
# WIFI FUNCTIONS
# -----------------------------

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)

    print("Resetting WiFi interface...")

    try:
        wlan.active(False)
        time.sleep(1)
    except Exception as error:
        print("WiFi reset warning:", error)

    wlan.active(True)
    time.sleep(1)

    if wlan.isconnected():
        print("Already connected to WiFi")
        print("ESP32 IP info:", wlan.ifconfig())
        return True

    print("Connecting to WiFi...")
    print("WiFi name:", WIFI_NAME)

    try:
        wlan.disconnect()
        time.sleep(1)
    except Exception as error:
        print("Disconnect warning:", error)

    try:
        wlan.connect(WIFI_NAME, WIFI_PASSWORD)
    except Exception as error:
        print("WiFi connect command failed:", error)
        return False

    start_time = time.ticks_ms()

    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start_time) > 45000:
            print("WiFi connection timeout")
            print("Status:", wlan.status())
            return False

        print("Waiting for WiFi...")
        print("Status:", wlan.status())
        time.sleep(1)

    print("WiFi connected!")
    print("ESP32 IP info:", wlan.ifconfig())

    return True


def reconnect_wifi_if_needed():
    wlan = network.WLAN(network.STA_IF)

    if wlan.isconnected():
        return True

    print("WiFi disconnected. Trying to reconnect...")
    return connect_wifi()


# -----------------------------
# SUPABASE SEND FUNCTION
# -----------------------------

def send_workout_to_supabase(weight_lbs, reps):
    """
    Sends completed workout set to Supabase.

    Supabase table should have these columns:
        machine_name
        reps
        user_slot
        weight_lbs

    This function does NOT send:
        device_id
        stack_slot
        tof_distance_mm

    Those values are only printed locally for debugging.
    """

    if not reconnect_wifi_if_needed():
        print("WiFi not connected. Skipping Supabase send.")
        return False

    payload = {
        "machine_name": MACHINE_NAME,
        "reps": reps,
        "user_slot": USER_SLOT,
        "weight_lbs": weight_lbs
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": "Bearer " + SUPABASE_KEY,
        "Prefer": "return=minimal"
    }

    print("")
    print("Sending workout to Supabase...")
    print("Payload:", payload)

    try:
        response = urequests.post(
            SUPABASE_URL,
            json=payload,
            headers=headers
        )

        status_code = response.status_code
        response_text = response.text

        print("Supabase HTTP status:", status_code)
        print("Supabase response:", response_text)

        response.close()

        if status_code == 200 or status_code == 201:
            print("Workout sent to Supabase successfully.")
            return True
        else:
            print("Supabase send failed.")
            return False

    except Exception as error:
        print("Failed to send workout to Supabase.")
        print("Error:", error)
        return False


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

    time.sleep(0.25)

    while boot_button_pressed():
        time.sleep(0.05)

    print("BOOT button pressed")
    print("Starting session")


# -----------------------------
# OPTIONAL FUTURE FEATURE
# Manual session stop using BOOT button
# -----------------------------
# Right now, the BOOT button only starts a session.
# Later, we can also let the user press BOOT again to end the set early.
#
# def should_stop_session():
#     if boot_button_pressed():
#         time.sleep(0.25)
#
#         while boot_button_pressed():
#             time.sleep(0.05)
#
#         print("BOOT button pressed again. Ending session manually.")
#         return True
#
#     return False
#
# Then inside count_reps(), add:
#
# if should_stop_session():
#     break


# -----------------------------
# TOF FUNCTIONS
# -----------------------------

def read_tof_mm():
    distance = tof.read()

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
        return None, None, None

    weight_lbs, error_mm, matched_distance, slot = weight_map.get_weight_with_error(distance_mm)

    print("")
    print("Average TOF distance:", distance_mm, "mm")
    print("Matched slot:", slot)
    print("Matched slot distance:", matched_distance, "mm")
    print("Distance error:", error_mm, "mm")
    print("Selected weight:", weight_lbs, "lbs")

    return weight_lbs, slot, distance_mm


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
    global wifi_ready

    print("")
    print("Track Weight full Supabase test")
    print("--------------------------------")

    init_sensors()

    print("")
    print("Connecting WiFi before workout sessions...")
    wifi_ready = connect_wifi()

    if wifi_ready:
        print("WiFi is ready. Workout data will be sent to Supabase.")
    else:
        print("WiFi is not ready. Workout data will only print.")

    while True:
        wait_for_button_press()

        selected_weight, stack_slot, tof_distance_mm = detect_selected_weight()

        if selected_weight is None:
            print("Skipping session because weight could not be detected")
            continue

        reps = count_reps()

        print("")
        print("Workout complete")
        print("----------------")
        print("Machine:", MACHINE_NAME)
        print("User slot:", USER_SLOT)
        print("Device ID:", DEVICE_ID)
        print("Weight:", selected_weight, "lbs")
        print("Stack slot:", stack_slot)
        print("TOF distance:", tof_distance_mm, "mm")
        print("Reps:", reps)

        if wifi_ready:
            send_success = send_workout_to_supabase(
                weight_lbs=selected_weight,
                reps=reps
            )

            if send_success:
                print("Workout data sent successfully.")
            else:
                print("Workout data failed to send.")
        else:
            print("WiFi not connected. Data was not sent.")

        print("")
        print("Ready for next BOOT button press.")

        time.sleep(1)


main()
