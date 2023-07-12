# Raspberry Pi Camera - ActionPi
Standalone Raspberry Pi Camera with different modes of operation and also a web interface

ActionPi allows Raspberry Pi to work as an underwater action camera. It offers a simple interface to capture photos, videos, and timelapse recordings underwater, using either a magnet and a piezo buzzer or a Flask-based web server.

The system is housed in a waterproof glass enclosure, allowing for safe usage underwater. I have added a magnet sensor that works as a button to select modes of operation, all triggered externally with a magnet.

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

1. Connect your Pi Camera to the Raspberry Pi.
2. Connect the magnetic sensor or a button to GPIO pin 10, 3.3V and GND.
3. Connect the piezo buzzer to GPIO pin 11. and GND.
4. I also recommend to use a small 5V fan.


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
