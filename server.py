from flask import Flask, send_from_directory, render_template, request, redirect, url_for
from zipfile import ZipFile
import os
import shutil
import threading
from datetime import datetime
from subprocess import call

app = Flask(__name__)

BASE_DIR = '/home/pi/camera'  # This should be the base directory where your files are located
DIRECTORIES = ['photos', 'videos', 'timelapses']

@app.route('/')
def index():
    all_files = {}
    for directory in DIRECTORIES:
        dir_path = os.path.join(BASE_DIR, directory)
        if os.path.exists(dir_path):
            all_files[directory] = os.listdir(dir_path)
        else:
            all_files[directory] = []
    return render_template('index.html', all_files=all_files)

# Capturing photo
@app.route('/start_photo_capture', methods=['GET'])
def start_photo_capture():
    capture_photo()
    return redirect(url_for('index'))

# Capturing video
@app.route('/start_video_capture', methods=['GET'])
def start_video_capture():
    duration = request.args.get('duration', default=1, type=int)
    record_video(duration)
    return redirect(url_for('index'))

# Capturing timelapse
@app.route('/start_timelapse', methods=['GET'])
def start_timelapse():
    interval = request.args.get('interval', default=1, type=int)
    duration = request.args.get('duration', default=1, type=int)

    capture_timelapse(interval, duration)
    return redirect(url_for('index'))

def capture_photo():
    # Create directory if it doesn't exist
    if not os.path.exists(BASE_DIR + "/photos"):
        os.mkdir(BASE_DIR + "/photos")

    # Generate the filename
    filename = datetime.now().strftime(BASE_DIR + "/photos/photo_%Y%m%d_%H%M%S.jpg")

    # Capture the photo
    os.system(f"libcamera-still -o {filename}")

def record_video(duration):
    # Create directory if it doesn't exist
    if not os.path.exists(BASE_DIR + "/videos"):
        os.mkdir(BASE_DIR + "/videos")

    # Generate filename
    filename_h264 = datetime.now().strftime(BASE_DIR + "/videos/video_%Y%m%d_%H%M%S.h264")
    filename_mp4 = filename_h264.replace('.h264', '.mp4')

    # Record the video
    os.system(f"libcamera-vid -t {duration * 1000} --framerate 24 --width 1920 --height 1080 -o {filename_h264}")
    
    # Convert the video to mp4
    os.system(f"ffmpeg -i {filename_h264} -vcodec copy {filename_mp4}")

    # Delete the original .h264 file
    os.remove(filename_h264)

def capture_timelapse(interval, duration):
    # Create directory if it doesn't exist
    if not os.path.exists(BASE_DIR + "/timelapses"):
        os.mkdir(BASE_DIR + "/timelapses")
    
    # Generate the folder and filename
    foldername = datetime.now().strftime(BASE_DIR + "/timelapses/timelapse_%Y%m%d_%H%M%S")
    os.mkdir(foldername)
    filename = foldername + "/image%04d.jpg"

    # Capture the timelapse
    os.system(f"libcamera-still -t {duration * 1000} --timelapse {interval * 1000} --framestart 1 -o {filename}")

@app.route('/download/<path:filepath>')
def download(filepath):
    full_filepath = os.path.join(BASE_DIR, filepath)
    # If it's a directory, zip it first
    if os.path.isdir(full_filepath):
        output_filename = f"{os.path.basename(filepath)}.zip"
        output_filepath = os.path.join(os.path.dirname(full_filepath), output_filename)
        # Create a Zip file
        with ZipFile(output_filepath, 'w') as zipf:
            for foldername, subfolders, filenames in os.walk(full_filepath):
                for filename in filenames:
                    # create complete filepath of file in directory
                    file_to_zip = os.path.join(foldername, filename)
                    # Add file to zip
                    zipf.write(file_to_zip, os.path.relpath(file_to_zip, full_filepath))
        return send_from_directory(*os.path.split(output_filepath), as_attachment=True)
    else:
        dirpath, filename = os.path.split(full_filepath)
        return send_from_directory(dirpath, filename, as_attachment=True)


@app.route('/download_all/<directory>')
def download_all(directory):
    dir_path = os.path.join(BASE_DIR, directory)
    output_filename = f"{directory}.zip"
    output_filepath = os.path.join(BASE_DIR, output_filename)

    # Create a Zip file
    with ZipFile(output_filepath, 'w') as zipf:
        for foldername, subfolders, filenames in os.walk(dir_path):
            for filename in filenames:
                # create complete filepath of file in directory
                filepath = os.path.join(foldername, filename)
                # Add file to zip
                zipf.write(filepath, os.path.relpath(filepath, dir_path))

    return send_from_directory(BASE_DIR, output_filename, as_attachment=True)

@app.route('/delete', methods=['POST'])
def delete():
    filepath = request.form.get('filepath')
    if filepath:
        file_to_delete = os.path.join(BASE_DIR, filepath)
        if os.path.exists(file_to_delete):
            if os.path.isdir(file_to_delete):
                shutil.rmtree(file_to_delete)
                # If the zip file exists, delete it too
                zip_file = file_to_delete + '.zip'
                if os.path.exists(zip_file):
                    os.remove(zip_file)
            else:
                os.remove(file_to_delete)
                # If the zip file of the file's directory exists, delete it too
                dir_zip_file = os.path.dirname(file_to_delete) + '.zip'
                if os.path.exists(dir_zip_file):
                    os.remove(dir_zip_file)
    return redirect(url_for('index'))

@app.route('/delete_all/<directory>', methods=['POST'])
def delete_all(directory):
    dir_path = os.path.join(BASE_DIR, directory)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
        # If the zip file exists, delete it too
        if os.path.exists(dir_path + '.zip'):
            os.remove(dir_path + '.zip')
    return redirect(url_for('index'))

@app.route('/shutdown', methods=['POST'])
def shutdown():
    call("sudo shutdown -h now", shell=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)