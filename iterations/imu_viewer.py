import serial
import time
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


PORT = "COM3"
BAUD = 115200


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

    K = np.array([
        [0, -z, y],
        [z, 0, -x],
        [-y, x, 0]
    ])

    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)

    return R


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
        [ w, -d, -h],
        [ w,  d, -h],
        [-w,  d, -h],
        [-w, -d,  h],
        [ w, -d,  h],
        [ w,  d,  h],
        [-w,  d,  h],
    ])

    faces = [
        [points[0], points[1], points[2], points[3]],
        [points[4], points[5], points[6], points[7]],
        [points[0], points[1], points[5], points[4]],
        [points[2], points[3], points[7], points[6]],
        [points[1], points[2], points[6], points[5]],
        [points[4], points[7], points[3], points[0]],
    ]

    return points, faces


def transform_faces(faces, R):
    transformed = []
    for face in faces:
        new_face = []
        for point in face:
            new_face.append(R @ point)
        transformed.append(new_face)
    return transformed


def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    _, box_faces = create_box()

    plt.ion()

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            parts = line.split(",")

            if len(parts) != 3:
                continue

            ax_raw = float(parts[0])
            ay_raw = float(parts[1])
            az_raw = float(parts[2])

            # Normalize acceleration vector
            accel = np.array([ax_raw, ay_raw, az_raw], dtype=float)
            accel = normalize(accel)

            # Use acceleration direction to orient the model
            R = rotation_from_z_to_vector(accel)

            ax.clear()

            rotated_faces = transform_faces(box_faces, R)

            box = Poly3DCollection(rotated_faces, alpha=0.7)
            ax.add_collection3d(box)

            # Draw X, Y, Z axes
            ax.quiver(0, 0, 0, 1, 0, 0, length=0.8, normalize=True)
            ax.quiver(0, 0, 0, 0, 1, 0, length=0.8, normalize=True)
            ax.quiver(0, 0, 0, 0, 0, 1, length=0.8, normalize=True)

            # Draw measured acceleration vector
            ax.quiver(0, 0, 0, accel[0], accel[1], accel[2], length=1.0, normalize=True)

            ax.text(0.85, 0, 0, "X")
            ax.text(0, 0.85, 0, "Y")
            ax.text(0, 0, 0.85, "Z vertical")

            ax.set_xlim([-1, 1])
            ax.set_ylim([-1, 1])
            ax.set_zlim([-1, 1])

            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")

            ax.set_title(f"IMU Orientation | X={ax_raw:.0f}, Y={ay_raw:.0f}, Z={az_raw:.0f}")

            plt.pause(0.01)

        except KeyboardInterrupt:
            print("Stopped.")
            break

        except Exception as e:
            print("Error:", e)


