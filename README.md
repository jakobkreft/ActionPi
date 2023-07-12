# Raspberry Pi Camera - ActionPi
Transform your Raspberry Pi into a standalone, high-performing underwater action camera with a distinctive, audio-based interface.

![actionpi](https://github.com/jakobkreft/ActionPi/assets/70409100/4d721f27-44cc-42d6-9a01-f8a979829875)


## Table of Contents
1. [Introduction](#introduction)
    - [Magnet Sensor and Piezo Buzzer](#magnet-sensor-and-piezo-buzzer)
    - [Modes of Operation](#modes-of-operation)
    - [Flask-based Web Server](#flask-based-web-server)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
    - [Install the required Python packages](#install-the-required-python-packages)
    - [Install the required system utilities](#install-the-required-system-utilities)
4. [Setting Up Hardware](#setting-up-hardware)
5. [Running the Scripts](#running-the-scripts)
6. [Setting Up the Web Server](#setting-up-the-web-server)
7. [Using the Web Server](#using-the-web-server)
8. [Setting Scripts to Run at Boot](#setting-scripts-to-run-at-boot)
9. [Conclusion](#conclusion)
10. [Contributing](#contributing)

## Introduction

The ActionPi project transforms your Raspberry Pi into an efficient underwater action camera capable of capturing images, recording videos, and conducting timelapse recordings. This camera system is unique for its dual modes of operation: an intuitive physical interface using a magnet sensor and a piezo buzzer, and a user-friendly, Flask-based web server.

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
https://github.com/jakobkreft/ActionPi.git
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
![actionpi_text](https://github.com/jakobkreft/ActionPi/assets/70409100/ae4ca36e-cbde-4c45-91ac-ff7da78c8395)


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

Transform your Raspberry Pi into a versatile action camera with ActionPi, whether for underwater use with a magnet or controlled via any web browser.

## Contributing

We welcome any contributions to improve ActionPi. Feel free to open an issue or submit a pull request.
