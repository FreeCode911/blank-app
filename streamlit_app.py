# app.py
import streamlit as st
import yt_dlp
import subprocess
from io import BytesIO
import re
import time

# App configuration
st.set_page_config(
    page_title="YouTube to MP3 Streamer",
    page_icon="🎵",
    layout="centered"
)

# Validate YouTube URL format
def validate_youtube_url(url):
    patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]{11}',
        r'^https?://youtu\.be/[\w-]{11}'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

# Main app
def main():
    st.title("🎵 YouTube to MP3 Streamer")
    st.caption("Stream YouTube audio as MP3 without downloading files")
    
    with st.form("converter_form"):
        url = st.text_input("Enter YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")
        submitted = st.form_submit_button("Stream MP3")
        
    if submitted:
        if not url:
            st.error("Please enter a YouTube URL")
            return
            
        if not validate_youtube_url(url):
            st.error("Invalid YouTube URL format")
            return
            
        try:
            with st.spinner("🔍 Extracting audio info..."):
                # Get audio info using yt-dlp
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    audio_url = info['url']
                    title = info.get('title', 'audio')
                    duration = info.get('duration', 0)
                    
                    # Get HTTP headers if available
                    headers = info.get('http_headers', {})
                    header_args = []
                    for k, v in headers.items():
                        header_args.extend(['-headers', f'{k}: {v}'])
            
            # Show video info
            st.subheader(f"🎧 {title}")
            if duration > 0:
                mins, secs = divmod(duration, 60)
                st.caption(f"⏱️ Duration: {int(mins)}:{int(secs):02d}")
            
            # Create FFmpeg command for MP3 conversion
            ffmpeg_cmd = [
                'ffmpeg',
                *header_args,
                '-i', audio_url,           # Input URL
                '-f', 'mp3',               # Output format
                '-acodec', 'libmp3lame',   # MP3 codec
                '-q:a', '2',               # Quality (0-9, 0=best)
                '-'                        # Output to stdout
            ]
            
            # Start FFmpeg process
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=4096
            )
            
            # Create download button
            mp3_bytes = BytesIO()
            download_placeholder = st.empty()
            
            # Stream conversion
            st.info("🔊 Streaming audio...")
            progress_bar = st.progress(0)
            start_time = time.time()
            
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                mp3_bytes.write(chunk)
                
                # Update progress based on time (since we don't know total size)
                if duration > 0:
                    elapsed = time.time() - start_time
                    progress = min(0.99, elapsed / duration)
                    progress_bar.progress(progress)
            
            # Finalize
            process.wait()
            if process.returncode != 0:
                st.error("Error during conversion")
                return
                
            progress_bar.progress(1.0)
            time.sleep(0.5)
            progress_bar.empty()
            
            mp3_bytes.seek(0)
            st.success("✅ Conversion complete!")
            
            # Create download button
            download_placeholder.download_button(
                label="⬇️ Download MP3",
                data=mp3_bytes,
                file_name=f"{title[:30]}.mp3".replace("/", "-"),
                mime="audio/mpeg"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.exception(e)

if __name__ == "__main__":
    main()