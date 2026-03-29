import board
import busio
import time
from adafruit_pca9685 import PCA9685

# ---------------- CONFIG ----------------
num_servos = 6
max_configurations = 10
step_delay = 0.01
step_size = 5

servo_channels = [0, 4, 8, 9, 12, 13]

# ---------------- INIT ----------------
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

current_positions = [375]*num_servos
saved_configurations = []
is_playing = False
loop_playback = False

# Initialize servos
for i in range(num_servos):
    pca.channels[servo_channels[i]].duty_cycle = current_positions[i]

print("Servo Controller Started...")

# ---------------- FUNCTIONS ----------------

def set_servo(index, value):
    current_positions[index] = value
    pca.channels[servo_channels[index]].duty_cycle = value


def smooth_move(target_positions):
    global current_positions
    
    moving = True
    while moving:
        moving = False
        for i in range(num_servos):
            if current_positions[i] < target_positions[i]:
                current_positions[i] += step_size
                moving = True
            elif current_positions[i] > target_positions[i]:
                current_positions[i] -= step_size
                moving = True

            pca.channels[servo_channels[i]].duty_cycle = current_positions[i]

        time.sleep(step_delay)


def save_pose():
    if len(saved_configurations) < max_configurations:
        saved_configurations.append(current_positions.copy())
        print("Pose saved:", current_positions)
    else:
        print("Memory full!")


def play_poses():
    global is_playing
    is_playing = True

    print("Playing poses...")
    while is_playing:
        for pose in saved_configurations:
            smooth_move(pose)
            time.sleep(0.5)

        if not loop_playback:
            break


def stop_playing():
    global is_playing
    is_playing = False
    print("Stopped.")


def reset_poses():
    global saved_configurations
    saved_configurations = []
    print("All poses cleared.")

# ---------------- MAIN LOOP ----------------

while True:
    cmd = input("Enter command: ").strip()

    if cmd == "S":
        save_pose()

    elif cmd == "P":
        play_poses()

    elif cmd == "R":
        reset_poses()

    elif cmd == "St":
        stop_playing()

    elif cmd == "LoopON":
        loop_playback = True
        print("Loop ON")

    elif cmd == "LoopOFF":
        loop_playback = False
        print("Loop OFF")

    elif "," in cmd:
        # Example: 0,400
        try:
            idx, val = map(int, cmd.split(","))
            set_servo(idx, val)
        except:
            print("Invalid format. Use: index,value")

    else:
        print("Unknown command")
