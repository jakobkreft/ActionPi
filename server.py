from flask import Flask, send_from_directory, render_template, request, redirect, url_for
from zipfile import ZipFile
import os
import shutil
import threading
from datetime import datetime
from subprocess import call
from PIL import Image

app = Flask(__name__)

BASE_DIR = '/home/pi/camera'  # This should be the base directory where your files are located
DIRECTORIES = ['photos', 'videos', 'timelapses']
THUMBNAIL_DIRECTORIES = {dir: os.path.join('thumbnails', dir) for dir in DIRECTORIES}

thumbnail_base_dir = os.path.join(BASE_DIR, 'thumbnails')
if not os.path.exists(thumbnail_base_dir):
    os.mkdir(thumbnail_base_dir)

@app.route('/')
def index():
    all_files = {}
    for directory in DIRECTORIES:
        dir_path = os.path.join(BASE_DIR, directory)
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            # Sort files by creation time, newest first
            files.sort(key=lambda x: os.path.getctime(os.path.join(dir_path, x)), reverse=True)
            all_files[directory] = files
        else:
            all_files[directory] = []
    return render_template('index.html', all_files=all_files)

@app.route('/thumbnail/<path:filepath>')
def get_thumbnail(filepath):
    thumbnail_path = os.path.join(BASE_DIR, filepath)
    dirpath, filename = os.path.split(thumbnail_path)
    return send_from_directory(dirpath, filename)



def create_thumbnail(input_image_path, output_image_path, size=(128, 128)):
    with Image.open(input_image_path) as img:
        img.thumbnail(size)
        img.save(output_image_path)

def create_video_thumbnail(video_path, thumbnail_path):
    # Use ffmpeg to capture a single frame from the video
    os.system(f"ffmpeg -i {video_path} -ss 00:00:01 -vframes 1 {thumbnail_path}")

    # Open the frame image and create a thumbnail
    with Image.open(thumbnail_path) as img:
        img.thumbnail((128, 128))  # Resize image in-place
        img.save(thumbnail_path)  # Overwrite the full-size frame with thumbnail


# Capturing photo
@app.route('/start_photo_capture', methods=['GET'])
def start_photo_capture():
    capture_photo()
    return redirect(url_for('index'))

def capture_photo():
    # Create directory if it doesn't exist
    if not os.path.exists(BASE_DIR + "/photos"):
        os.mkdir(BASE_DIR + "/photos")

    # Generate the filename
    filename = datetime.now().strftime(BASE_DIR + "/photos/photo_%Y%m%d_%H%M%S.jpg")

    # Capture the photo
    os.system(f"libcamera-still -o {filename}")

    thumbnail_dir = os.path.join(thumbnail_base_dir, 'photos')
    if not os.path.exists(thumbnail_dir):
        os.mkdir(thumbnail_dir)

    # Create the thumbnail
    thumbnail_filename = os.path.join(thumbnail_dir, os.path.basename(filename))
    create_thumbnail(filename, thumbnail_filename)


# Capturing video
@app.route('/start_video_capture', methods=['GET'])
def start_video_capture():
    duration = request.args.get('duration', default=1, type=int)
    record_video(duration)
    return redirect(url_for('index'))

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


    thumbnail_dir = os.path.join(thumbnail_base_dir, 'videos')
    if not os.path.exists(thumbnail_dir):
        os.mkdir(thumbnail_dir)

    # Create the thumbnail
    thumbnail_filename = os.path.join(thumbnail_dir, os.path.basename(filename_mp4).replace('.mp4', '.jpg'))
    create_video_thumbnail(filename_mp4, thumbnail_filename)

# Capturing timelapse
@app.route('/start_timelapse', methods=['GET'])
def start_timelapse():
    interval = request.args.get('interval', default=1, type=int)
    duration = request.args.get('duration', default=1, type=int)

    capture_timelapse(interval, duration)
    return redirect(url_for('index'))

def capture_timelapse(interval, duration):
    # Create directory if it doesn't exist
    timelapse_dir = os.path.join(BASE_DIR, "timelapses")
    if not os.path.exists(timelapse_dir):
        os.mkdir(timelapse_dir)
    
    # Generate the folder and filename
    foldername = datetime.now().strftime(timelapse_dir + "/timelapse_%Y%m%d_%H%M%S")
    os.mkdir(foldername)
    filename = os.path.join(foldername, "image%04d.jpg")

    # Capture the timelapse
    os.system(f"libcamera-still -t {duration * 1000} --timelapse {interval * 1000} --framestart 1 -o {filename}")

    # Create the thumbnail for the first image in the sequence
    first_image = os.path.join(foldername, "image0001.jpg")

    # Create directory for thumbnails if it doesn't exist
    thumbnail_dir = os.path.join(thumbnail_base_dir, 'timelapses')
    if not os.path.exists(thumbnail_dir):
        os.mkdir(thumbnail_dir)

    # Create the thumbnail
    thumbnail_filename = os.path.join(thumbnail_dir, os.path.basename(foldername) + ".jpg")
    create_thumbnail(first_image, thumbnail_filename)

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
                # Remove directory and its thumbnail
                shutil.rmtree(file_to_delete)
                # If the zip file exists, delete it too
                zip_file = file_to_delete + '.zip'
                if os.path.exists(zip_file):
                    os.remove(zip_file)
            else:
                # Remove file and its thumbnail
                os.remove(file_to_delete)
                thumbnail = os.path.join(BASE_DIR, 'thumbnails', filepath.split('/')[0], os.path.basename(file_to_delete))
                if os.path.exists(thumbnail):
                    os.remove(thumbnail)

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
        zip_path = dir_path + '.zip'
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        # If corresponding thumbnails directory exists, delete it too
        thumbnail_dir_path = os.path.join(BASE_DIR, THUMBNAIL_DIRECTORIES[directory])
        if os.path.exists(thumbnail_dir_path):
            shutil.rmtree(thumbnail_dir_path)
        
    return redirect(url_for('index'))


@app.route('/shutdown', methods=['POST'])
def shutdown():
    call("sudo shutdown -h now", shell=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)