# Raspberry Pi Camera - ActionPi
Standalone Raspberry Pi Camera with different modes of operation and also a web interface

![actionpi](https://github.com/jakobkreft/ActionPi/assets/70409100/f379d3ce-c501-487c-a150-d21ae6b52ed5)


# Underwater ActionPi: An Underwater Action Camera with Raspberry Pi

## Introduction

Underwater ActionPi is an innovative project that transforms a Raspberry Pi into a high-functioning underwater action camera. Designed and developed to capture images, record videos, and execute timelapse recordings in an underwater environment. 

The standout feature of this underwater action camera is its intuitive interface. The system can be operated via two different modes. The first one involves the use of a magnet sensor and a piezo buzzer, while the second utilizes a Flask-based web server. 

### Magnet Sensor and Piezo Buzzer

The system's operation is facilitated with the help of a magnet sensor that acts as a functional button to select the operational modes. An external magnet can be used to interact with this sensor, making it easy to control the camera while it's secured inside the waterproof enclosure. This makes the system suitable for use underwater. 

A piezo buzzer is incorporated in the system to provide audio feedback on the mode selected. Different tones or melodies are associated with each mode, making it intuitive to understand the status of the system just by listening to the sounds. This feature enhances the usability of the system, providing an additional layer of interactivity to ensure the user can easily discern between operational modes. 

### Modes of operation
There are four main modes: 'photo', 'video', 'timelapse', and 'shutdown'. Each mode is cycled through a continuous loop and indicated by a unique melody played through the piezo buzzer. The detection of a magnet (acting as a button press) during a specific melody finalizes the selection of the corresponding mode.

1. **Photo Mode:** When the 'photo' mode melody is being played through the piezo buzzer, if the button press is detected, it selects this mode. Once selected, a photo is captured, with a specific melody being played to indicate the action.

2. **Timelapse Mode:** As the 'timelapse' mode melody plays, if the button press is detected, the Raspberry Pi starts taking photos for a duration which can be further specified by the user. The duration specification process also involves the use of the piezo buzzer and button press detection. Different sets of short beeps are played corresponding to different recording durations. Once the desired beep set (duration) is played, the user can wait and finalize the recording duration and the recording of the timelapse starts.

3. **Video Mode:** Similar to the 'timelapse' mode, the 'video' mode waits for the button press during its unique melody to be selected. Once selected, a video is recorded for a duration chosen by the user in a similar fashion as described in the 'timelapse' mode.

4. **Shutdown Mode:** This mode, when chosen through a button press during its melody, initiates a shutdown procedure. A final confirmation is requested from the user, signaled by a single beep for 10 seconds. If the button is pressed within this time, the Raspberry Pi is shut down.

The interaction between the piezo buzzer and the button press mechanism provides an innovative, audio-based user interface. This design allows the user to control the operation of their underwater action camera without the need for a traditional visual interface. After the execution of each action corresponding to the selected mode, the script returns to the beginning of the mode selection loop, allowing for continuous and repeated use.

### Flask-based Web Server

As an alternative to the physical magnet sensor interface, the system also supports a Flask-based web server interface. Flask, a lightweight web framework for Python, is used to run a local web server on the Raspberry Pi. This server provides a web page that can be accessed from any device connected to the same network, offering an interactive interface for controlling the camera. The web interface provides the ability to initiate capture of photos, videos, or timelapse recordings, as well as reviewing, downloading, or deleting the recorded files. This approach provides an advanced level of control and interaction, particularly useful for monitoring and controlling the system remotely. 

Underwater ActionPi combines advanced technology with user-friendly interfaces, creating an efficient and enjoyable underwater action camera. Its innovative design and the convenience it offers make it a significant leap forward in the realm of underwater photography and videography. 


## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Setting Up Hardware](#setting-up-hardware)
4. [Running the Scripts](#running-the-scripts)
5. [Setting Up the Web Server](#setting-up-the-web-server)
6. [Using the Web Server](#using-the-web-server)
7. [Setting Scripts to Run at Boot](#setting-scripts-to-run-at-boot)
8. [Conclusion](#conclusion)
9. [Contributing](#contributing)

## Prerequisites

To use Underwater ActionPi, you need the following:

1. A Raspberry Pi with WiFi capability
2. A Pi Camera module
3. A waterproof enclosure for the Raspberry Pi and Camera module
4. A magnetic sensor to serve as a button *(explain what picture goes here)*

Before you start, make sure your Raspberry Pi OS is up to date, and you have Python3 and pip installed.

## Installation

To get started, clone this repository to your Raspberry Pi.

```bash
git clone https://github.com/jakobkreft/ActionPi.git
cd ActionPi
```

### Install the required Python packages

First, ensure that pip, Python's package installer, is installed on your Raspberry Pi. If not, you can install it with:

```bash
sudo apt-get install python3-pip
```

Then install the Python packages that are required for this project. We'll install each one individually:

Flask is a micro web framework for Python, it's needed to run the web server that allows you to control the camera from a web page:

```bash
pip3 install flask
```

RPi.GPIO is a library to control the General Purpose Input and Output pins of the Raspberry Pi:

```bash
pip3 install RPi.GPIO
```

### Install the required system utilities

There are also some system utilities that are required. These are not Python libraries, but programs that need to be installed on the Raspberry Pi.

`ffmpeg` is a utility to handle multimedia data, it can convert between different file formats. We need this to convert the video files from the Raspberry Pi camera to an mp4 format:

```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

`libcamera` is a library that provides a software stack to access camera devices on Linux-based systems like the Raspberry Pi. We need the `libcamera-tools` package that provides command line utilities to interact with the camera:

```bash
sudo apt-get install libcamera-tools
```

Please ensure these packages are installed correctly before proceeding. The Flask and RPi.GPIO libraries are needed to run the Python script, and the `ffmpeg` and `libcamera-tools` utilities are used within the script to interact with the camera and the video files.

## Setting Up Hardware
![actionpi_text](https://github.com/jakobkreft/ActionPi/assets/70409100/f0000abd-131c-41b6-b6e2-8d196d90365b)


1. Connect your Pi Camera to the Raspberry Pi.
2. Connect the magnetic sensor or a button to GPIO pin 10, 3.3V and GND.
3. Connect the piezo buzzer to GPIO pin 11. and GND.
4. I also recommend to use a small 5V fan.

![wiring](https://github.com/jakobkreft/ActionPi/assets/70409100/ca2b8448-4772-48cd-9b8e-2e93ad4f6086)

Place your Raspberry Pi and Camera inside the waterproof enclosure, ensuring that the magnetic sensor is positioned to easily interact with an external magnet.

## Running the Scripts

You can run the camera script with the following command:

```bash
python3 camera.py
```

The script will start, waiting for the button (magnet sensor) to be triggered. Depending on the pattern of presses, the script will execute different actions such as taking a photo, recording a video or starting a timelapse.

## Setting Up the Web Server

To set up the web server, run the following command:

```bash
python3 server.py
```

This will start the Flask web server on port 8000. You can access it by navigating to the IP address of your Raspberry Pi in a web browser on the same network, followed by `:8000`.

## Using the Web Server

The web server provides a more comprehensive and interactive way to control the Raspberry Pi Camera. It provides an interface to capture photos, videos, and timelapses, as well as to manage (download or delete) the captured files.
![ActionPiCamera](https://github.com/jakobkreft/ActionPi/assets/70409100/aa58d77d-f926-4b22-aeda-e2a39844f04f)

## Setting Scripts to Run at Boot

To make your Underwater ActionPi ready whenever you power it on, you can set the scripts to run at boot. You can do this by adding a crontab entry. Open crontab with:

```bash
crontab -e
```

And add the following lines:

```bash
@reboot python3 /home/pi/ActionPi/camera.py > /home/pi/ActionPi/camera.log 2>&1 &
@reboot python3 /home/pi/ActionPi/server.py > /home/pi/ActionPi/server.log 2>&1 &
```

 Now, both scripts will start running after the Raspberry Pi boots up.

## Conclusion

With ActionPi you can transform your Raspberry Pi into an action camera. You can even use it underwater with the use of the magnet. Or simply use your phone or any web browser to control the camera.

## Contributing

Contributions to improve Underwater ActionPi are welcome. Feel free to open an issue or submit a pull request.
