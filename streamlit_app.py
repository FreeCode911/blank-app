import streamlit as st
import yt_dlp
import subprocess
from io import BytesIO
import re
import requests
from flask import Flask, Response, request as flask_request
import threading

# Create Flask app for API
api_app = Flask(__name__)

# API endpoint
@api_app.route('/convert', methods=['GET'])
def convert_api():
    """API endpoint for YouTube to MP3 conversion"""
    video_url = flask_request.args.get('url')
    if not video_url:
        return Response("Missing URL parameter", status=400)
    
    if not re.match(r'^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}', video_url):
        return Response("Invalid YouTube URL", status=400)
    
    try:
        # Get audio info using yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            title = info.get('title', 'audio')
            headers = info.get('http_headers', {})
        
        # FFmpeg command for MP3 conversion
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', audio_url,
            '-f', 'mp3',
            '-acodec', 'libmp3lame',
            '-q:a', '2',
            '-'
        ]
        
        # Add headers if available
        if headers:
            header_args = []
            for k, v in headers.items():
                header_args.extend(['-headers', f'{k}: {v}'])
            ffmpeg_cmd[1:1] = header_args
        
        # Run FFmpeg and stream output
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        # Stream response
        def generate():
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        
        return Response(
            generate(),
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': f'attachment; filename="{title[:50]}.mp3"',
                'Cache-Control': 'no-store'
            }
        )
    
    except Exception as e:
        return Response(f"Error: {str(e)}", status=500)

# Run Flask API in background thread
def run_api():
    api_app.run(port=5000, host='0.0.0.0', debug=False, use_reloader=False)

threading.Thread(target=run_api, daemon=True).start()

# Streamlit UI
st.set_page_config(
    page_title="YouTube to MP3 Converter",
    page_icon="🎧",
    layout="centered"
)

st.title("🎧 YouTube to MP3 Converter")
st.caption("Stream YouTube audio as MP3 - UI + API")


# UI conversion section
with st.form("converter_form"):
    url = st.text_input("YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")
    submitted = st.form_submit_button("Convert to MP3")
    
if submitted:
    if not url:
        st.error("Please enter a YouTube URL")
        st.stop()
    
    if not re.match(r'^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}', url):
        st.error("Invalid YouTube URL format")
        st.stop()
    
    try:
        # Use our own API to handle conversion
        api_url = f"http://localhost:5000/convert?url={url}"
        
        with st.spinner("🔍 Extracting audio info..."):
            # First get video title
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'audio')
            
            # Start streaming conversion
            response = requests.get(api_url, stream=True)
            
            if response.status_code != 200:
                st.error(f"API Error: {response.text}")
                st.stop()
            
            # Stream to download button
            mp3_bytes = BytesIO()
            for chunk in response.iter_content(chunk_size=4096):
                mp3_bytes.write(chunk)
            
            mp3_bytes.seek(0)
            
            st.success("✅ Conversion complete!")
            st.audio(mp3_bytes, format='audio/mp3')
            
            st.download_button(
                label="⬇️ Download MP3",
                data=mp3_bytes,
                file_name=f"{title[:50]}.mp3".replace("/", "-"),
                mime="audio/mpeg"
            )
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.exception(e)