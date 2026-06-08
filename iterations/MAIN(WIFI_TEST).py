# wifi_test.py
# Simple ESP32 WiFi test for Track Weight
# Sends fake workout data to your laptop Flask server

import network
import time
import urequests


# -----------------------------
# WIFI SETTINGS
# -----------------------------

WIFI_NAME = "MONGOTHEFINFERB 1812"
WIFI_PASSWORD = "ADD here"


# -----------------------------
# SERVER SETTINGS
# -----------------------------
# This is your laptop Flask server address from PyCharm.
# Your Flask server showed:
# Running on http://10.0.0.30:5000
#
# The ESP32 must send to the /workout route.

SERVER_URL = "http://add here"


# -----------------------------
# WIFI FUNCTION
# -----------------------------

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Already connected to WiFi")
        print("ESP32 IP info:", wlan.ifconfig())
        return True

    print("Connecting to WiFi...")
    print("WiFi name:", WIFI_NAME)

    wlan.connect(WIFI_NAME, WIFI_PASSWORD)

    start_time = time.ticks_ms()

    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start_time) > 15000:
            print("WiFi connection timeout")
            return False

        print("Waiting for WiFi...")
        time.sleep(1)

    print("WiFi connected!")
    print("ESP32 IP info:", wlan.ifconfig())

    return True


# -----------------------------
# SEND TEST DATA
# -----------------------------

def send_test_workout():
    data = {
        "device_id": "track_weight_esp32_test",
        "weight_lbs": 50,
        "reps": 12
    }

    print("")
    print("Sending test workout data...")
    print(data)

    try:
        response = urequests.post(
            SERVER_URL,
            json=data
        )

        print("Server status code:", response.status_code)
        print("Server response:")
        print(response.text)

        response.close()

        return True

    except Exception as error:
        print("Failed to send data")
        print("Error:", error)
        return False


# -----------------------------
# MAIN
# -----------------------------

def main():
    print("")
    print("Track Weight ESP32 WiFi Test")
    print("----------------------------")

    wifi_ready = connect_wifi()

    if wifi_ready:
        send_test_workout()
    else:
        print("Could not connect to WiFi. Test stopped.")

    print("")
    print("WiFi test complete.")


main()
