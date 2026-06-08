import serial
import time
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# -----------------------------
# Serial settings
# -----------------------------
PORT = "COM3"
BAUD = 115200


# -----------------------------
# Helper functions
# -----------------------------
def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def rotation_from_z_to_vector(target_z):
    """
    Creates a rotation matrix that rotates the model's local Z axis
    to match the measured acceleration direction.
    """
    target_z = normalize(target_z)

    original_z = np.array([0.0, 0.0, 1.0])
    axis = np.cross(original_z, target_z)
    axis_norm = np.linalg.norm(axis)

    if axis_norm < 1e-6:
        return np.eye(3)

    axis = axis / axis_norm
    angle = np.arccos(np.clip(np.dot(original_z, target_z), -1.0, 1.0))

    x, y, z = axis

    k_matrix = np.array([
        [0, -z, y],
        [z, 0, -x],
        [-y, x, 0]
    ])

    rotation_matrix = (
        np.eye(3)
        + np.sin(angle) * k_matrix
        + (1 - np.cos(angle)) * (k_matrix @ k_matrix)
    )

    return rotation_matrix


def create_box(width=1.0, depth=0.6, height=0.15):
    """
    Creates a simple rectangular 3D box to represent the IMU board.
    Z is vertical.
    """
    w = width / 2
    d = depth / 2
    h = height / 2

    points = np.array([
        [-w, -d, -h],
        [w, -d, -h],
        [w, d, -h],
        [-w, d, -h],
        [-w, -d, h],
        [w, -d, h],
        [w, d, h],
        [-w, d, h],
    ])

    faces = [
        [points[0], points[1], points[2], points[3]],
        [points[4], points[5], points[6], points[7]],
        [points[0], points[1], points[5], points[4]],
        [points[2], points[3], points[7], points[6]],
        [points[1], points[2], points[6], points[5]],
        [points[4], points[7], points[3], points[0]],
    ]

    return faces


def transform_faces(faces, rotation_matrix):
    transformed = []

    for face in faces:
        new_face = []
        for point in face:
            new_face.append(rotation_matrix @ point)
        transformed.append(new_face)

    return transformed


def read_latest_valid_line(ser):
    """
    Reads serial data and keeps only the newest valid line.
    This helps reduce visual lag if the ESP32 is printing faster
    than matplotlib can update.
    """
    latest_line = None

    while ser.in_waiting:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if line:
                latest_line = line

        except Exception:
            pass

    return latest_line


def parse_imu_line(line):
    """
    Expected ESP32 format:
    ax,ay,az,gx,gy,gz

    Example:
    -236,512,16080,12,-8,3
    """
    parts = line.split(",")

    if len(parts) < 3:
        return None

    try:
        ax_raw = float(parts[0])
        ay_raw = float(parts[1])
        az_raw = float(parts[2])

        gx_raw = float(parts[3]) if len(parts) > 3 else 0.0
        gy_raw = float(parts[4]) if len(parts) > 4 else 0.0
        gz_raw = float(parts[5]) if len(parts) > 5 else 0.0

        return ax_raw, ay_raw, az_raw, gx_raw, gy_raw, gz_raw

    except ValueError:
        return None


def draw_scene(ax, box_faces, accel, raw_values):
    ax.clear()

    rotation_matrix = rotation_from_z_to_vector(accel)
    rotated_faces = transform_faces(box_faces, rotation_matrix)

    box = Poly3DCollection(rotated_faces, alpha=0.7)
    ax.add_collection3d(box)

    # Draw world axes
    ax.quiver(0, 0, 0, 1, 0, 0, length=0.8, normalize=True)
    ax.quiver(0, 0, 0, 0, 1, 0, length=0.8, normalize=True)
    ax.quiver(0, 0, 0, 0, 0, 1, length=0.8, normalize=True)

    # Draw measured acceleration vector
    ax.quiver(
        0, 0, 0,
        accel[0], accel[1], accel[2],
        length=1.0,
        normalize=True
    )

    ax.text(0.85, 0, 0, "X")
    ax.text(0, 0.85, 0, "Y")
    ax.text(0, 0, 0.85, "Z vertical")

    ax.set_xlim([-1, 1])
    ax.set_ylim([-1, 1])
    ax.set_zlim([-1, 1])

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax_raw, ay_raw, az_raw, gx_raw, gy_raw, gz_raw = raw_values

    ax.set_title(
        f"IMU Orientation\n"
        f"Accel: X={ax_raw:.0f}, Y={ay_raw:.0f}, Z={az_raw:.0f} | "
        f"Gyro: X={gx_raw:.0f}, Y={gy_raw:.0f}, Z={gz_raw:.0f}"
    )


def main():
    print("Opening serial port...")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.05)
    except serial.SerialException as e:
        print("Could not open serial port.")
        print("Make sure Thonny and PuTTY are closed.")
        print("Error:", e)
        return

    time.sleep(2)
    ser.reset_input_buffer()

    print("Connected to ESP32.")
    print("Waiting for IMU data...")

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    box_faces = create_box()

    plt.ion()

    last_update = time.time()

    try:
        while True:
            line = read_latest_valid_line(ser)

            if line is None:
                plt.pause(0.001)
                continue

            parsed = parse_imu_line(line)

            if parsed is None:
                print("Ignored bad line:", line)
                continue

            ax_raw, ay_raw, az_raw, gx_raw, gy_raw, gz_raw = parsed

            accel = np.array([ax_raw, ay_raw, az_raw], dtype=float)
            accel = normalize(accel)

            # Limit redraw rate to reduce lag
            now = time.time()
            if now - last_update >= 0.03:
                draw_scene(
                    ax,
                    box_faces,
                    accel,
                    (ax_raw, ay_raw, az_raw, gx_raw, gy_raw, gz_raw)
                )

                plt.pause(0.001)
                last_update = now

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()