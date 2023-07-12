import RPi.GPIO as GPIO
import threading
import time
import os
from datetime import datetime
import sys

# Add a base directory for your paths
base_dir = "/home/pi/camera/"


# Pin configurations
BUTTON_PIN = 10
BUZZER_PIN = 11

# Note frequencies
notes = {
    'C': 261.63,
    'D': 293.66,
    'E': 329.63,
    'F': 349.23,
    'G': 392,
    'A': 440,
    'B': 493.88,
    'C2': 523.25,
    'R': 1  # Rest
}

# Tunes for different modes with different timings
tunes = {
    "photo": [('D', 0.4), ('F', 0.4), ('A', 0.4)],
    "timelapse": [('D', 0.3), ('F', 0.1), ('A', 0.3), ('F', 0.1)],
    "video": [('C', 0.2), ('D', 0.2), ('E', 0.2)],
    "shutdown": [('G', 0.3), ('C2', 0.3)],
}

# State variables
selected_mode = None
button_pressed = threading.Event()

# Set up GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Initialize PWM for the buzzer
p = GPIO.PWM(BUZZER_PIN, 100)
p.start(1)
p.ChangeDutyCycle(0) # stop the buzzer initially

# Function to play a note
def play_note(note, duration):
    frequency = notes.get(note, 1)
    p.ChangeFrequency(frequency)
    p.ChangeDutyCycle(90 if note != 'R' else 0)  # Make rest notes silent
    time.sleep(duration)

# Function to play a beep and pause at the beginning
def initial_beep():
    while not button_pressed.is_set():
        play_note('A', 0.5)
        p.ChangeDutyCycle(0)
        time.sleep(0.5)

# Function to play a tune
def play_tune(mode, tune):
    global selected_mode
    start_time = time.time()
    p.ChangeDutyCycle(0)  # stop the buzzer before starting the tune
    time.sleep(1)  # delay between tunes
    while True:
        for note, duration in tune:
            if button_pressed.is_set():
                button_pressed.clear()
                selected_mode = mode
                return True
            play_note(note, duration)
        if time.time() - start_time >= 6:  # 10 seconds to decide
            break
    p.ChangeDutyCycle(0)  # stop the buzzer after finishing the tune
    return False


def recording_duration():
    duration_index = 0  # index 0-7 maps to 1, 2, 4, 8, 16, 32, 64, 128 minutes
    while True:
        duration = 2**duration_index
        print(f"Set recording time to {duration} minute(s)")
        start_time = time.time()
        while time.time() - start_time < 10:  # 10 seconds to decide
            # Number of short beeps
            for i in range(duration_index + 1):
                if button_pressed.is_set():
                    button_pressed.clear()
                    duration_index = (duration_index + 1) % 8  # Loop back to 0 after reaching 7
                    break  # Break the inner loop
                play_note('A', 0.1)  # Short beep
                p.ChangeDutyCycle(0)  # Short pause
                time.sleep(0.1)
            else:
                # Long pause
                p.ChangeDutyCycle(0)
                time.sleep(0.7)
                continue  # Continue if the inner loop wasn't broken
            break  # Break the outer loop
        else:
            p.ChangeDutyCycle(0)
            return duration  # Return the recording time in minutes

# Add shutdown function
def shutdown():
    start_time = time.time()
    while time.time() - start_time < 10:  # 10 seconds to confirm
        if button_pressed.is_set():
            p.ChangeDutyCycle(0)
            os.system("sudo shutdown -h now")  # shutdown the Pi
            return  # Exit function in case shutdown does not happen immediately
        play_note('A', 0.2)  # Single beep
        p.ChangeDutyCycle(0)  # Pause
        time.sleep(0.8)  # Wait for the remainder of the second
    p.ChangeDutyCycle(0)  # Make rest notes silent
    p.stop()  # Stop PWM output
    GPIO.cleanup()  # Cleanup GPIO channels
    sys.exit(0)  # Exit the Python script if the button is not pressed within 10 seconds

# Function to play melody
def play_melody():
    global play_melody_flag
    melody = [('C', 0.2), ('D', 0.2), ('E', 0.2), ('F', 0.2), ('G', 0.2), ('A', 0.15), ('C2', 0.1)]
    while play_melody_flag:
        p.ChangeDutyCycle(0)  # Make rest notes silent
        time.sleep(2)
        for note, duration in melody:
            play_note(note, duration)



def capture_photo():
    global play_melody_flag
    # Set flag to start playing melody
    play_melody_flag = True
    # Start melody in a separate thread
    threading.Thread(target=play_melody).start()
    # Create directory if it doesn't exist
    if not os.path.exists(base_dir + "photos"):
        os.mkdir(base_dir + "photos")
    
    # Generate the filename
    filename = datetime.now().strftime(base_dir + "photos/photo_%Y%m%d_%H%M%S.jpg")

    # Capture the photo
    os.system(f"libcamera-still -o {filename}")
    # Set flag to stop playing melody
    play_melody_flag = False

def record_video(duration):
    global play_melody_flag
    # Set flag to start playing melody
    play_melody_flag = True
    # Start melody in a separate thread
    threading.Thread(target=play_melody).start()
    # Create directory if it doesn't exist
    if not os.path.exists(base_dir + "videos"):
        os.mkdir(base_dir + "videos")

    # Generate filename
    filename_h264 = datetime.now().strftime(base_dir + "videos/video_%Y%m%d_%H%M%S.h264")
    filename_mp4 = filename_h264.replace('.h264', '.mp4')

    # Record the video
    os.system(f"libcamera-vid -t {duration * 60 * 1000} --framerate 24 --width 1920 --height 1080 -o {filename_h264}")
    
    # Convert the video to mp4
    os.system(f"ffmpeg -i {filename_h264} -vcodec copy {filename_mp4}")

    # Delete the original .h264 file
    os.remove(filename_h264)

    # Set flag to stop playing melody
    play_melody_flag = False


# Function to capture a timelapse with melody
def capture_timelapse(duration):

    global play_melody_flag
    # Set flag to start playing melody
    play_melody_flag = True
    # Start melody in a separate thread
    threading.Thread(target=play_melody).start()
    # Create directory if it doesn't exist
    if not os.path.exists(base_dir + "timelapses"):
        os.mkdir(base_dir + "timelapses")
    
    # Generate the folder and filename
    foldername = datetime.now().strftime(base_dir + "timelapses/timelapse_%Y%m%d_%H%M%S")
    os.mkdir(foldername)
    filename = foldername + "/image%04d.jpg"

    # Capture the timelapse
    os.system(f"libcamera-still -t {duration * 60000} --timelapse 2000 --framestart 1 -o {filename}")

    # Set flag to stop playing melody
    play_melody_flag = False

# Button press handler
def button_press(channel):
    button_pressed.set()

# Set the callback for button press
GPIO.add_event_detect(BUTTON_PIN, GPIO.RISING, callback=button_press, bouncetime=200)






# Modify the main loop to handle the shutdown mode
while True:
    # Play initial beep
    initial_beep()
    # Clear the initial button press event
    button_pressed.clear()
    for mode, tune in tunes.items():
        print(f"Select {mode} mode")
        if play_tune(mode, tune):
            print(f"{mode} mode selected")
            if mode == 'video':
                duration = recording_duration()
                print(f"Recording {mode} for {duration} minute(s)")
                record_video(duration)
            elif mode == 'photo':
                print("Taking a photo")
                capture_photo()
            elif mode == 'timelapse':
                duration = recording_duration()
                print(f"Capturing a timelapse for {duration} minute(s)")
                capture_timelapse(duration)
            elif mode == 'shutdown':
                shutdown()  # start shutdown procedure
            p.ChangeDutyCycle(0)  # Make rest notes silent
            time.sleep(10)  # 10 second delay after selection
            p.ChangeDutyCycle(90)  # Resume notes
            # Clear the button press event after each action
            button_pressed.clear()
            # Break out of the for loop to start the mode selection from the beginning
            break
        time.sleep(1)  # Short delay between modes


# Clean up
p.stop()
GPIO.cleanup()