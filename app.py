from flask import Flask, jsonify, request
import os
import requests
from moviepy.editor import VideoFileClip, concatenate_videoclips
import whisper
import firebase_admin
from firebase_admin import credentials, storage, firestore
from flask_cors import CORS
import tempfile

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate(
    '/Users/vamsikeshwaran/vamsicorp/Backend/framewise-1e85c-firebase-adminsdk-3v8ba-372dfdbbdb.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'framewise-1e85c.appspot.com'
})
db = firestore.client()
bucket = storage.bucket()

CLIPS_DIR = './clips'
if not os.path.exists(CLIPS_DIR):
    os.makedirs(CLIPS_DIR)


def download_video(url, output_path):
    response = requests.get(url, stream=True)
    video_path = os.path.join(output_path, 'downloaded_video.mp4')
    with open(video_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
    return video_path


def video_to_audio(video_path, audio_path):
    video_clip = VideoFileClip(video_path)
    video_clip.audio.write_audiofile(audio_path)
    video_clip.close()


def speech_to_text_with_timestamps(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, verbose=True, word_timestamps=True)
    return result['segments']


def create_clips(segments, video_path):
    video_clip = VideoFileClip(video_path)
    clip_info = []

    for i, segment in enumerate(segments):
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text'].strip()

        clip_path = os.path.join(CLIPS_DIR, f'clip_{i + 1}.mp4')
        clip = video_clip.subclip(start_time, end_time)
        clip.write_videofile(clip_path, codec='libx264')
        blob = bucket.blob(f'clips/clip_{i + 1}.mp4')
        blob.upload_from_filename(clip_path)
        blob.make_public()
        clip_url = blob.public_url
        clip_info.append({
            'start_time': start_time,
            'end_time': end_time,
            'sentence': text,
            'clip_path': clip_url
        })

    video_clip.close()
    return clip_info


@app.route('/process_video', methods=['POST'])
def process_video():
    data = request.json
    video_url = data.get('video_url')

    if not video_url:
        return jsonify({'error': 'No video URL provided'}), 400

    output_path = './downloads'
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    video_path = os.path.join(output_path, 'downloaded_video.mp4')
    audio_path = os.path.join(output_path, 'extracted_audio.wav')

    print("Downloading video...")
    download_video(video_url, output_path)

    print("Extracting audio from video...")
    video_to_audio(video_path, audio_path)

    print("Converting speech to text with timestamps...")
    segments = speech_to_text_with_timestamps(audio_path)

    print("Creating clips...")
    clip_info = create_clips(segments, video_path)

    return jsonify(clip_info)


def download_videos(urls):
    video_paths = []
    for i, url in enumerate(urls):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        response = requests.get(url, stream=True)
        with open(temp_file.name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        video_paths.append(temp_file.name)
    return video_paths


@app.route('/concatenate_videos', methods=['POST'])
def concatenate_videos():
    data = request.get_json()
    video_urls = data.get('video_urls')

    if not video_urls:
        return jsonify({'error': 'No video URLs provided'}), 400

    try:
        video_paths = download_videos(video_urls)
        video_clips = [VideoFileClip(path) for path in video_paths]
        concatenated_clip = concatenate_videoclips(video_clips)

        concatenated_video_file = tempfile.NamedTemporaryFile(
            delete=False, suffix='.mp4')
        concatenated_clip.write_videofile(
            concatenated_video_file.name, codec='libx264')

        blob = bucket.blob(
            f'concatenated_videos/{os.path.basename(concatenated_video_file.name)}')
        blob.upload_from_filename(concatenated_video_file.name)
        blob.make_public()

        for path in video_paths:
            os.remove(path)
        os.remove(concatenated_video_file.name)

        return jsonify({'concatenated_video_url': blob.public_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
