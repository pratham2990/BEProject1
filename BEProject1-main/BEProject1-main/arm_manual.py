import time
import board
import busio
from adafruit_pca9685 import PCA9685

# ================== CONFIG ==================
NUM_SERVOS = 5
MAX_CONFIGS = 10
STEP_DELAY = 0.01
STEP_SIZE = 1

# Removed base servo (channel 0)
SERVO_CHANNELS = [4, 8, 9, 12, 13]

# Storage
saved_configurations = []
current_positions = [375] * NUM_SERVOS

is_playing = False
loop_playback = False
stop_playing = False
current_pose_index = 0

# ================== SETUP ==================
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 60

# Initialize servos
for i in range(NUM_SERVOS):
    pca.channels[SERVO_CHANNELS[i]].duty_cycle = current_positions[i] * 16

print("Raspberry Pi Servo Controller Started...")

# ================== FUNCTIONS ==================

def map_angle_to_pwm(angle):
    return int(150 + (angle / 180.0) * (600 - 150))


def move_smooth(servo_index, target_pwm):
    global current_positions

    current_pwm = current_positions[servo_index]

    if target_pwm > current_pwm:
        step_range = range(current_pwm, target_pwm, STEP_SIZE)
    else:
        step_range = range(current_pwm, target_pwm, -STEP_SIZE)

    for pos in step_range:
        pca.channels[SERVO_CHANNELS[servo_index]].duty_cycle = pos * 16
        time.sleep(STEP_DELAY)

    current_positions[servo_index] = target_pwm

    print(f"Servo {servo_index+1} → PWM: {target_pwm}")


def process_command(command):
    global is_playing, loop_playback, stop_playing

    if command == "S":
        save_pose()

    elif command == "P":
        start_playback()

    elif command == "R":
        reset_poses()

    elif command == "St":
        stop_playback()

    elif command == "LoopON":
        loop_playback = True
        print("Loop enabled")

    elif command == "LoopOFF":
        loop_playback = False
        print("Loop disabled")

    elif "," in command:
        try:
            servo, angle = command.split(",")
            servo_index = int(servo) - 1

            if servo_index >= NUM_SERVOS:
                print("Invalid servo index (base removed)")
                return

            angle = float(angle)
            pwm_val = map_angle_to_pwm(angle)

            move_smooth(servo_index, pwm_val)

        except:
            print("Invalid format")

    else:
        print("Unknown command")


# ================== POSE FUNCTIONS ==================

def save_pose():
    if len(saved_configurations) < MAX_CONFIGS:
        saved_configurations.append(current_positions.copy())
        print(f"Pose saved ({len(saved_configurations)})")
    else:
        print("Memory full")


def start_playback():
    global is_playing, stop_playing, current_pose_index

    if len(saved_configurations) == 0:
        print("No poses saved")
        return

    is_playing = True
    stop_playing = False
    current_pose_index = 0

    print("Playback started")


def play_next_pose():
    global current_pose_index, is_playing

    if current_pose_index < len(saved_configurations):
        pose = saved_configurations[current_pose_index]

        print(f"Playing pose {current_pose_index+1}")

        for i in range(NUM_SERVOS):
            move_smooth(i, pose[i])

        time.sleep(1)
        current_pose_index += 1

    else:
        is_playing = False
        print("Playback finished")


def play_loop():
    global stop_playing

    for pose in saved_configurations:
        for i in range(NUM_SERVOS):
            move_smooth(i, pose[i])

        time.sleep(1)

        if stop_playing:
            break


def stop_playback():
    global stop_playing, is_playing
    stop_playing = True
    is_playing = False
    print("Playback stopped")


def reset_poses():
    global saved_configurations, is_playing, loop_playback

    saved_configurations = []
    is_playing = False
    loop_playback = False

    print("All poses cleared")


# ================== MAIN LOOP ==================

while True:
    command = input("Enter command: ").strip()

    process_command(command)

    if is_playing and not stop_playing:
        if loop_playback:
            play_loop()
        else:
            play_next_pose()
