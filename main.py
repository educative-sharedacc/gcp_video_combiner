from flask import Flask, request, jsonify
import os, tempfile, uuid
from yt_dlp import YoutubeDL
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from google.cloud import storage

app = Flask(__name__)

BUCKET_NAME = 'veo_output_bucket/combined-videos'

def download_media(url, output_path):
    ydl_opts = {'outtmpl': output_path, 'quiet': True, 'format': 'best[ext=mp4]/best'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def upload_to_gcs(local_file, remote_name):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(remote_name)
    blob.upload_from_filename(local_file)
    blob.make_public()
    return blob.public_url

@app.route('/combine', methods=['POST'])
def combine():
    data = request.get_json()
    video_urls = data.get('video_urls')
    music_url = data.get('music_url')

    temp_dir = tempfile.mkdtemp()
    video_files = []

    for i, url in enumerate(video_urls):
        out = os.path.join(temp_dir, f'video_{i}.mp4')
        download_media(url, out)
        video_files.append(out)

    music_file = os.path.join(temp_dir, 'music.mp4')
    download_media(music_url, music_file)

    clips = [VideoFileClip(v) for v in video_files]
    final_clip = concatenate_videoclips(clips)
    audio = AudioFileClip(music_file).subclip(0, final_clip.duration)
    final_clip = final_clip.set_audio(audio)

    final_output = os.path.join(temp_dir, f'{uuid.uuid4()}.mp4')
    final_clip.write_videofile(final_output, codec='libx264', audio_codec='aac')

    gcs_url = upload_to_gcs(final_output, os.path.basename(final_output))
    return jsonify({'output_url': gcs_url})
