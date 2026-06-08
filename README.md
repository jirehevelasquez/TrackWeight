# TrackWeight
gym tracking hardware and software

TrackWeight is a smart gym tracking prototype designed to automatically record the selected weight, rep count, machine used, and workout session data from weight-stack exercise machines. The goal of the project is to reduce the friction of manual workout logging by using embedded hardware, sensors, WiFi communication, and a cloud database workflow.

This project was developed as a proof-of-concept for an automatic workout tracking system that could be installed on gym machines and connected to a user-facing fitness dashboard.

## Project Overview

Many gym users want to track their progress, but manual tracking can be tedious, inconsistent, and disruptive during workouts. TrackWeight addresses this problem by using a hardware sensor device attached to a weight-stack machine.

The prototype detects:

* The selected weight on a weight-stack machine
* The number of completed repetitions
* The machine being used
* The active workout session
* A timestamped workout event sent to a cloud database

The system was designed around a simple workflow:

1. User starts a workout session.
2. The device reads the selected weight using a time-of-flight distance sensor.
3. The device counts repetitions using IMU motion data.
4. The ESP32 sends the completed workout set over WiFi.
5. Workout data is stored in Supabase.
6. The data can be displayed in a mobile or web dashboard.

## Hardware

The prototype was built around an ESP32 microcontroller and external sensors.

Main hardware components:

* ESP32 development board
* VL53L0X time-of-flight distance sensor
* MPU6050 IMU
* Weight-stack machine prototype setup
* WiFi connection for cloud communication
* Supabase backend for workout event storage

## Software

The software was written in MicroPython for the ESP32.

### Main Files

| File            | Purpose                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------ |
| `main.py`       | Main session logic, WiFi connection, sensor integration, rep counting, and Supabase upload |
| `IMU.py`        | MPU6050 accelerometer/gyroscope driver with filtered IMU readings                          |
| `TOF.py`        | VL53L0X time-of-flight sensor driver                                                       |
| `weight_map.py` | Converts measured distance into weight-stack slot and selected weight                      |
| `boot.py`       | ESP32 boot file                                                                            |

## System Architecture

TrackWeight uses two sensor inputs:

### 1. Weight Detection

The VL53L0X time-of-flight sensor measures distance to determine where the weight selector pin is located. The measured distance is compared against a calibrated home position and plate spacing to estimate the selected stack slot.

The selected slot is converted into weight using:

```python
weight = start_weight_lbs + (slot * weight_step_lbs)
```

### 2. Rep Detection

The MPU6050 IMU measures motion of the weight stack during exercise. The system first collects a baseline while the machine is still. During the workout, filtered acceleration data is compared against that baseline.

A rep is counted when:

* Motion exceeds a set threshold.
* The weight stack returns near the baseline.
* A minimum time between reps has passed.

This helps reduce false counts from noise or vibration.

### 3. Cloud Upload

After a workout set is complete, the ESP32 sends the workout data to Supabase using an HTTP POST request.

Example workout data:

```json
{
  "machine_name": "Leg Extension",
  "reps": 10,
  "user_slot": 1,
  "weight": 50,
  "created_at": "2026-01-01T12:00:00Z"
}
```

## Customer and Market Validation

As part of the project, the team conducted customer discovery, surveys, and MVP validation. The project explored both gym members and gym owners as potential users.

Key validation findings:

* 87.8% of surveyed users were interested or very interested in automatic workout tracking.
* 85.4% were open to paying or potentially paying for automated workout tracking.
* 85.4% used weight-stack machines for at least half of their workouts.
* Customers wanted tracking to require little to no manual effort.
* Gym operators were interested in machine utilization data and member-retention analytics.

These findings shifted the product direction from only targeting individual gym members to also targeting gyms and fitness facilities as the primary customers.

## Prototype Milestones

The proof-of-concept demonstrated:

* Smart pin CAD completed
* Rep detection successful
* Weight identification successful
* ESP32 WiFi transmission successful
* Cloud database integration successful
* Mobile dashboard concept operational

## Setup Notes

This repository is intended to document the embedded prototype code. Before running the project, update the WiFi and Supabase settings in `main.py`.

For public repositories, do not commit private credentials. Use placeholders such as:

```python
WIFI_NAME = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"
```

## Calibration Parameters

The weight detection system depends on calibration values in `main.py`:

```python
HOME_DISTANCE_MM = 120
PLATE_THICKNESS_MM = 25
START_WEIGHT_LBS = 10
WEIGHT_STEP_LBS = 10
MAX_SLOTS = 9
```

These values should be adjusted for the actual machine geometry.

## Current Status

TrackWeight is a working proof-of-concept prototype. The current system can detect selected weight, count reps, and send workout data to a Supabase backend.

Future improvements include:

* Finalizing the hardware enclosure
* Adding NFC or user identification
* Improving battery life
* Improving durability for gym environments
* Expanding the analytics dashboard
* Testing with a local gym or real weight-stack machine
* Improving calibration tools for different machines

## Key Takeaways

This project combined embedded systems, sensor integration, customer discovery, product design, and cloud-connected data logging. The most valuable engineering lesson was that a successful product prototype requires both technical validation and customer validation. The hardware had to work reliably, but the user experience also had to be simple enough that gym members would actually use it during workouts.

## Disclaimer

This repository is for portfolio and prototype documentation purposes. The code should be reviewed, sanitized, and calibrated before being used on real gym equipment.
