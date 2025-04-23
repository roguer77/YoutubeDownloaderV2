import os
import time
import logging
import random
import re
from urllib.parse import urlparse, parse_qs
import yt_dlp
import shutil
import tempfile
import pytube
import requests
import subprocess

logger = logging.getLogger(__name__)

class YoutubeDownloader:
    """YouTube video downloader with anti-bot measures and fallback mechanisms"""
    
    def __init__(self):
        """Initialize with rate limiting and retry settings"""
        self.RATE_LIMIT_DELAY = 2  # seconds between requests
        self.RETRY_COUNT = 3  # number of retries
        self.RETRY_DELAY = 5  # seconds between retries
        self.last_request_time = 0
        
        # Check if ffmpeg is available
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check if ffmpeg is available on the system"""
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.debug("ffmpeg is available")
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            logger.warning("ffmpeg is not available, some audio features may be limited")
            return False
    
    def _rate_limit(self):
        """Apply rate limiting to avoid detection as bot"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.RATE_LIMIT_DELAY:
            # Add a small random delay for further obfuscation
            delay = self.RATE_LIMIT_DELAY - elapsed + random.uniform(0.1, 1.0)
            logger.debug(f"Rate limiting applied, sleeping for {delay:.2f} seconds")
            time.sleep(delay)
        
        self.last_request_time = time.time()
    
    def _extract_video_id(self, url):
        """Extract YouTube video ID from URL"""
        parsed_url = urlparse(url)
        
        # Handle youtu.be URLs
        if parsed_url.netloc == 'youtu.be':
            return parsed_url.path.lstrip('/')
        
        # Handle regular youtube.com URLs
        if parsed_url.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            query = parse_qs(parsed_url.query)
            return query.get('v', [None])[0]
        
        return None
    
    def _is_playlist(self, url):
        """Check if the URL is a playlist"""
        parsed_url = urlparse(url)
        if parsed_url.netloc in ('youtube.com', 'www.youtube.com'):
            query = parse_qs(parsed_url.query)
            return 'list' in query
        return False
    
    def get_video_info(self, url):
        """Get information about the video"""
        self._rate_limit()
        
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        
        is_playlist = self._is_playlist(url)
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'no_color': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if is_playlist and '_type' in info and info['_type'] == 'playlist':
                    # Handle playlist
                    result = {
                        'is_playlist': True,
                        'title': info.get('title', 'Playlist'),
                        'entries': [],
                        'formats': [
                            {'format_id': 'best', 'format_note': 'Best Quality (Video)'},
                            {'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'format_note': '1080p (High Quality)'},
                            {'format_id': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'format_note': '720p (Medium Quality)'},
                            {'format_id': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'format_note': '480p (Low Quality)'},
                            {'format_id': 'bestvideo[height<=360]+bestaudio/best[height<=360]', 'format_note': '360p (Low Quality)'}
                        ],
                        'audio_formats': [
                            {'format_id': 'bestaudio', 'format_note': 'Best Quality (Audio)'},
                            {'format_id': 'bestaudio[ext=m4a]/bestaudio', 'format_note': 'M4A (High Quality)'},
                            {'format_id': 'bestaudio[ext=mp3]/bestaudio', 'format_note': 'MP3 (High Quality)'},
                            {'format_id': 'bestaudio[abr>=128]/bestaudio', 'format_note': 'MP3 (128kbps)'},
                            {'format_id': 'bestaudio[abr>=96]/bestaudio', 'format_note': 'MP3 (96kbps)'}
                        ]
                    }
                    
                    # Add playlist entries (limit to first 10 for UI preview)
                    for idx, entry in enumerate(info.get('entries', [])):
                        if idx < 10 and entry:  # Only process first 10 videos for preview
                            result['entries'].append({
                                'title': entry.get('title', f'Video {idx+1}'),
                                'id': entry.get('id', ''),
                                'duration': entry.get('duration', 0),
                                'thumbnail': entry.get('thumbnail', '')
                            })
                    
                    result['playlist_count'] = info.get('playlist_count', len(info.get('entries', [])))
                    return result
                else:
                    # Handle single video
                    # Process formats into quality groups
                    formats = info.get('formats', [])
                    
                    # Extract the desired formats for the UI
                    video_formats = []
                    added_resolutions = set()  # Track which resolutions we've already added
                    
                    # First, add a "best quality" option
                    video_formats.append({'format_id': 'best', 'format_note': 'Best Quality (Video)'})
                    
                    # Process combined formats (those with both video and audio)
                    combined_formats = []
                    for f in formats:
                        # Only include formats with both video and audio
                        if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                            height = f.get('height', 0)
                            width = f.get('width', 0)
                            format_id = f.get('format_id', '')
                            format_note = f.get('format_note', '')
                            ext = f.get('ext', 'mp4')
                            tbr = f.get('tbr', 0)  # Bitrate in KBps
                            
                            # Create a format display name with resolution and bitrate
                            if height > 0:
                                resolution = f"{width}x{height}"
                                display_name = f"{height}p"
                                if tbr > 0:
                                    display_name += f" ({round(tbr)}kbps)"
                                display_name += f" - {ext.upper()}"
                                
                                # Add the format
                                combined_formats.append({
                                    'format_id': format_id,
                                    'format_note': display_name,
                                    'height': height,
                                    'width': width,
                                    'ext': ext,
                                    'tbr': tbr
                                })
                    
                    # Sort by height (resolution) then bitrate
                    combined_formats.sort(key=lambda x: (-x['height'], -x.get('tbr', 0)))
                    
                    # Add the formats, avoiding pure duplicates
                    for fmt in combined_formats:
                        video_formats.append({
                            'format_id': fmt['format_id'],
                            'format_note': fmt['format_note']
                        })
                    
                    # If no specific formats were found, ensure "best" option is present
                    if len(video_formats) <= 1:
                        # We already added "best" earlier, so check if that's all we have
                        video_formats = [{'format_id': 'best', 'format_note': 'Best Quality (Video)'}]
                        
                        # Add some sensible defaults
                        video_formats.extend([
                            {'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'format_note': '1080p (High Quality)'},
                            {'format_id': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'format_note': '720p (Medium Quality)'},
                            {'format_id': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'format_note': '480p (Low Quality)'},
                        ])
                    
                    # Audio formats with more options
                    audio_formats = [
                        {'format_id': 'bestaudio', 'format_note': 'Best Quality (Audio)'},
                        {'format_id': 'bestaudio[ext=m4a]/bestaudio', 'format_note': 'M4A (High Quality)'},
                        {'format_id': 'bestaudio[ext=mp3]/bestaudio', 'format_note': 'MP3 (High Quality)'},
                        {'format_id': 'bestaudio[abr>=128]/bestaudio', 'format_note': 'MP3 (128kbps)'},
                        {'format_id': 'bestaudio[abr>=96]/bestaudio', 'format_note': 'MP3 (96kbps)'}
                    ]
                    
                    return {
                        'is_playlist': False,
                        'id': info.get('id', video_id),
                        'title': info.get('title', 'YouTube Video'),
                        'description': info.get('description', ''),
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'formats': video_formats,
                        'audio_formats': audio_formats,
                        'uploader': info.get('uploader', ''),
                        'view_count': info.get('view_count', 0)
                    }
        
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            
            # Try fallback with pytube
            try:
                logger.debug("Trying pytube fallback for video info")
                if is_playlist:
                    # Handle playlist with pytube
                    from pytube import Playlist
                    p = Playlist(url)
                    result = {
                        'is_playlist': True,
                        'title': p.title if hasattr(p, 'title') else 'Playlist',
                        'entries': [],
                        'formats': [
                            {'format_id': 'best', 'format_note': 'Best Quality (Video)'},
                            {'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'format_note': '1080p (High Quality)'},
                            {'format_id': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'format_note': '720p (Medium Quality)'},
                            {'format_id': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'format_note': '480p (Low Quality)'},
                            {'format_id': 'bestvideo[height<=360]+bestaudio/best[height<=360]', 'format_note': '360p (Low Quality)'}
                        ],
                        'audio_formats': [
                            {'format_id': 'bestaudio', 'format_note': 'Best Quality (Audio)'},
                            {'format_id': 'bestaudio[ext=m4a]/bestaudio', 'format_note': 'M4A (High Quality)'},
                            {'format_id': 'bestaudio[ext=mp3]/bestaudio', 'format_note': 'MP3 (High Quality)'},
                            {'format_id': 'bestaudio[abr>=128]/bestaudio', 'format_note': 'MP3 (128kbps)'},
                            {'format_id': 'bestaudio[abr>=96]/bestaudio', 'format_note': 'MP3 (96kbps)'}
                        ]
                    }
                    
                    # Add playlist entries (limit to first 10 for UI preview)
                    for idx, video_url in enumerate(p.video_urls[:10]):
                        try:
                            v = pytube.YouTube(video_url)
                            result['entries'].append({
                                'title': v.title,
                                'id': v.video_id,
                                'duration': v.length,
                                'thumbnail': v.thumbnail_url
                            })
                        except:
                            # Skip problematic videos
                            continue
                    
                    result['playlist_count'] = len(p.video_urls)
                    return result
                else:
                    # Handle single video with pytube
                    v = pytube.YouTube(url)
                    return {
                        'is_playlist': False,
                        'id': v.video_id,
                        'title': v.title,
                        'description': v.description,
                        'duration': v.length,
                        'thumbnail': v.thumbnail_url,
                        'formats': [
                            {'format_id': 'best', 'format_note': 'Best Quality (Video)'},
                            {'format_id': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'format_note': '1080p (High Quality)'},
                            {'format_id': 'bestvideo[height<=720]+bestaudio/best[height<=720]', 'format_note': '720p (Medium Quality)'},
                            {'format_id': 'bestvideo[height<=480]+bestaudio/best[height<=480]', 'format_note': '480p (Low Quality)'},
                            {'format_id': 'bestvideo[height<=360]+bestaudio/best[height<=360]', 'format_note': '360p (Low Quality)'}
                        ],
                        'audio_formats': [
                            {'format_id': 'bestaudio', 'format_note': 'Best Quality (Audio)'},
                            {'format_id': 'bestaudio[ext=m4a]/bestaudio', 'format_note': 'M4A (High Quality)'},
                            {'format_id': 'bestaudio[ext=mp3]/bestaudio', 'format_note': 'MP3 (High Quality)'},
                            {'format_id': 'bestaudio[abr>=128]/bestaudio', 'format_note': 'MP3 (128kbps)'},
                            {'format_id': 'bestaudio[abr>=96]/bestaudio', 'format_note': 'MP3 (96kbps)'}
                        ],
                        'uploader': v.author,
                        'view_count': v.views
                    }
            except Exception as fallback_error:
                logger.error(f"Pytube fallback also failed: {str(fallback_error)}")
                raise ValueError(f"Could not retrieve video information: {str(e)}")
    
    def download_video(self, url, format_id='best', output_path=None, progress_hook=None, playlist=False):
        """Download a YouTube video"""
        self._rate_limit()
        
        if not output_path:
            output_path = tempfile.mkdtemp()
        
        # Generate a sanitized output filename template
        output_template = os.path.join(output_path, '%(title)s.%(ext)s')
        
        # Configure options for yt-dlp
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_template,
            'noplaylist': not playlist,
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        # Add progress hook if provided
        if progress_hook:
            ydl_opts['progress_hooks'] = [progress_hook]
        
        # If it's a playlist and format selection is a named quality, map it
        if playlist and format_id in ['1080p', '720p', '480p', '360p']:
            if format_id == '1080p':
                ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            elif format_id == '720p':
                ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            elif format_id == '480p':
                ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
            elif format_id == '360p':
                ydl_opts['format'] = 'bestvideo[height<=360]+bestaudio/best[height<=360]'
        
        # For playlists, create a ZIP file
        if playlist:
            # Create a separate temporary directory for playlist items
            playlist_temp_dir = tempfile.mkdtemp()
            ydl_opts['outtmpl'] = os.path.join(playlist_temp_dir, '%(title)s.%(ext)s')
        
        video_file = None
        for attempt in range(self.RETRY_COUNT):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    download_info = ydl.extract_info(url, download=True)
                    
                    if playlist:
                        # Create a ZIP file for playlist
                        import zipfile
                        
                        # Get playlist title or use 'playlist' as fallback
                        playlist_title = download_info.get('title', 'playlist')
                        playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                        
                        zip_filename = os.path.join(output_path, f"{playlist_title}.zip")
                        with zipfile.ZipFile(zip_filename, 'w') as zipf:
                            for root, _, files in os.walk(playlist_temp_dir):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    # Add file to zip (with arcname to avoid folder structure in zip)
                                    zipf.write(file_path, os.path.basename(file_path))
                        
                        # Clean up temporary playlist directory
                        shutil.rmtree(playlist_temp_dir)
                        video_file = zip_filename
                    else:
                        # Handle single video download
                        if 'requested_downloads' in download_info:
                            video_file = download_info['requested_downloads'][0]['filepath']
                        else:
                            # If direct filepath not available, try to find by expected filename
                            title = download_info.get('title', 'video')
                            ext = download_info.get('ext', 'mp4')
                            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
                            
                            possible_file = os.path.join(output_path, f"{sanitized_title}.{ext}")
                            if os.path.exists(possible_file):
                                video_file = possible_file
                
                # If we got here, download was successful
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"Download attempt {attempt+1} failed: {error_msg}")
                
                # Check for bot detection or sign-in requirements
                if "sign in" in error_msg or "not a bot" in error_msg:
                    logger.info("Bot detection triggered, trying alternative approach")
                    
                    try:
                        # Try with a different user agent and referer
                        fallback_opts = ydl_opts.copy()
                        fallback_opts['http_headers'] = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36',
                            'Referer': 'https://www.youtube.com/'
                        }
                        
                        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                            download_info = ydl.extract_info(url, download=True)
                            
                            if playlist:
                                # Same ZIP handling as above
                                import zipfile
                                playlist_title = download_info.get('title', 'playlist')
                                playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                                
                                zip_filename = os.path.join(output_path, f"{playlist_title}.zip")
                                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                    for root, _, files in os.walk(playlist_temp_dir):
                                        for file in files:
                                            file_path = os.path.join(root, file)
                                            zipf.write(file_path, os.path.basename(file_path))
                                
                                shutil.rmtree(playlist_temp_dir)
                                video_file = zip_filename
                            else:
                                # Handle single video
                                if 'requested_downloads' in download_info:
                                    video_file = download_info['requested_downloads'][0]['filepath']
                                else:
                                    title = download_info.get('title', 'video')
                                    ext = download_info.get('ext', 'mp4')
                                    sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
                                    
                                    possible_file = os.path.join(output_path, f"{sanitized_title}.{ext}")
                                    if os.path.exists(possible_file):
                                        video_file = possible_file
                        
                        # If we got here, alternative approach worked
                        break
                    
                    except Exception as alt_error:
                        logger.warning(f"Alternative approach also failed: {str(alt_error)}")
                        # Continue to pytube fallback below if this is the last attempt
                
                # If this is the last attempt, try pytube as fallback
                if attempt == self.RETRY_COUNT - 1:
                    try:
                        logger.info("Trying pytube as final fallback for download")
                        
                        if playlist:
                            from pytube import Playlist
                            p = Playlist(url)
                            
                            # Create a ZIP file for playlist
                            import zipfile
                            playlist_title = p.title if hasattr(p, 'title') else 'playlist'
                            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                            
                            zip_filename = os.path.join(output_path, f"{playlist_title}.zip")
                            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                # Download each video in playlist
                                for video_url in p.video_urls:
                                    try:
                                        v = pytube.YouTube(video_url)
                                        
                                        # Select stream based on format_id
                                        if format_id == '1080p':
                                            stream = v.streams.filter(progressive=True, res="1080p").first() or v.streams.get_highest_resolution()
                                        elif format_id == '720p':
                                            stream = v.streams.filter(progressive=True, res="720p").first() or v.streams.get_highest_resolution()
                                        elif format_id == '480p':
                                            stream = v.streams.filter(progressive=True, res="480p").first() or v.streams.get_highest_resolution()
                                        elif format_id == '360p':
                                            stream = v.streams.filter(progressive=True, res="360p").first() or v.streams.get_highest_resolution()
                                        else:
                                            stream = v.streams.get_highest_resolution()
                                        
                                        if stream:
                                            file_path = stream.download(output_path=playlist_temp_dir)
                                            zipf.write(file_path, os.path.basename(file_path))
                                            os.remove(file_path)  # Clean up after adding to zip
                                    except Exception as video_error:
                                        logger.warning(f"Error downloading playlist video: {str(video_error)}")
                                        continue
                            
                            # Clean up temporary playlist directory
                            shutil.rmtree(playlist_temp_dir)
                            video_file = zip_filename
                        else:
                            # Single video download with pytube
                            v = pytube.YouTube(url, on_progress_callback=self._pytube_progress_callback(progress_hook))
                            
                            # Select stream based on format_id
                            if format_id == '1080p':
                                stream = v.streams.filter(progressive=True, res="1080p").first() or v.streams.get_highest_resolution()
                            elif format_id == '720p':
                                stream = v.streams.filter(progressive=True, res="720p").first() or v.streams.get_highest_resolution()
                            elif format_id == '480p':
                                stream = v.streams.filter(progressive=True, res="480p").first() or v.streams.get_highest_resolution()
                            elif format_id == '360p':
                                stream = v.streams.filter(progressive=True, res="360p").first() or v.streams.get_highest_resolution()
                            else:
                                stream = v.streams.get_highest_resolution()
                            
                            if stream:
                                video_file = stream.download(output_path=output_path)
                                
                        # If we got here, pytube fallback worked
                        if video_file:
                            break
                    
                    except Exception as pytube_error:
                        logger.error(f"Pytube fallback also failed: {str(pytube_error)}")
                        # All methods failed, will raise error after loop
                
                # Wait before retrying
                if attempt < self.RETRY_COUNT - 1:
                    sleep_time = self.RETRY_DELAY * (attempt + 1)  # Progressive backoff
                    logger.info(f"Waiting {sleep_time} seconds before retry...")
                    time.sleep(sleep_time)
        
        if not video_file or not os.path.exists(video_file):
            raise ValueError("Failed to download video after multiple attempts. The video may be unavailable or restricted.")
        
        return video_file
    
    def download_audio(self, url, output_path=None, progress_hook=None, playlist=False):
        """Download audio from a YouTube video"""
        self._rate_limit()
        
        if not output_path:
            output_path = tempfile.mkdtemp()
        
        # Generate a sanitized output filename template
        output_template = os.path.join(output_path, '%(title)s.%(ext)s')
        
        # Configure options for yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'noplaylist': not playlist,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        # Add progress hook if provided
        if progress_hook:
            ydl_opts['progress_hooks'] = [progress_hook]
        
        # For playlists, create a ZIP file
        if playlist:
            # Create a separate temporary directory for playlist items
            playlist_temp_dir = tempfile.mkdtemp()
            ydl_opts['outtmpl'] = os.path.join(playlist_temp_dir, '%(title)s.%(ext)s')
        
        audio_file = None
        for attempt in range(self.RETRY_COUNT):
            try:
                # Check if ffmpeg is available for audio extraction
                if not self.ffmpeg_available:
                    # If ffmpeg is not available, modify options to skip audio extraction
                    ydl_opts.pop('postprocessors', None)
                    ydl_opts['format'] = 'bestaudio'
                    logger.warning("ffmpeg not available, downloading audio without conversion")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    download_info = ydl.extract_info(url, download=True)
                    
                    if playlist:
                        # Create a ZIP file for playlist
                        import zipfile
                        
                        # Get playlist title or use 'playlist' as fallback
                        playlist_title = download_info.get('title', 'playlist')
                        playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                        
                        zip_filename = os.path.join(output_path, f"{playlist_title}_audio.zip")
                        with zipfile.ZipFile(zip_filename, 'w') as zipf:
                            for root, _, files in os.walk(playlist_temp_dir):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    # Add file to zip (with arcname to avoid folder structure in zip)
                                    zipf.write(file_path, os.path.basename(file_path))
                        
                        # Clean up temporary playlist directory
                        shutil.rmtree(playlist_temp_dir)
                        audio_file = zip_filename
                    else:
                        # Handle single audio download
                        if 'requested_downloads' in download_info:
                            audio_file = download_info['requested_downloads'][0]['filepath']
                        else:
                            # If direct filepath not available, try to find by expected filename
                            title = download_info.get('title', 'audio')
                            ext = 'mp3' if self.ffmpeg_available else download_info.get('ext', 'mp3')
                            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
                            
                            possible_file = os.path.join(output_path, f"{sanitized_title}.{ext}")
                            if os.path.exists(possible_file):
                                audio_file = possible_file
                
                # If we got here, download was successful
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"Audio download attempt {attempt+1} failed: {error_msg}")
                
                # Check for bot detection or sign-in requirements
                if "sign in" in error_msg or "not a bot" in error_msg:
                    logger.info("Bot detection triggered, trying alternative approach")
                    
                    try:
                        # Try with a different user agent and referer
                        fallback_opts = ydl_opts.copy()
                        fallback_opts['http_headers'] = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36',
                            'Referer': 'https://www.youtube.com/'
                        }
                        
                        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                            download_info = ydl.extract_info(url, download=True)
                            
                            if playlist:
                                # Same ZIP handling as above
                                import zipfile
                                playlist_title = download_info.get('title', 'playlist')
                                playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                                
                                zip_filename = os.path.join(output_path, f"{playlist_title}_audio.zip")
                                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                    for root, _, files in os.walk(playlist_temp_dir):
                                        for file in files:
                                            file_path = os.path.join(root, file)
                                            zipf.write(file_path, os.path.basename(file_path))
                                
                                shutil.rmtree(playlist_temp_dir)
                                audio_file = zip_filename
                            else:
                                # Handle single audio
                                if 'requested_downloads' in download_info:
                                    audio_file = download_info['requested_downloads'][0]['filepath']
                                else:
                                    title = download_info.get('title', 'audio')
                                    ext = 'mp3' if self.ffmpeg_available else download_info.get('ext', 'mp3')
                                    sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
                                    
                                    possible_file = os.path.join(output_path, f"{sanitized_title}.{ext}")
                                    if os.path.exists(possible_file):
                                        audio_file = possible_file
                        
                        # If we got here, alternative approach worked
                        break
                    
                    except Exception as alt_error:
                        logger.warning(f"Alternative approach also failed: {str(alt_error)}")
                        # Continue to pytube fallback below if this is the last attempt
                
                # If this is the last attempt, try pytube as fallback
                if attempt == self.RETRY_COUNT - 1:
                    try:
                        logger.info("Trying pytube as final fallback for audio download")
                        
                        if playlist:
                            from pytube import Playlist
                            p = Playlist(url)
                            
                            # Create a ZIP file for playlist
                            import zipfile
                            playlist_title = p.title if hasattr(p, 'title') else 'playlist'
                            playlist_title = re.sub(r'[^\w\-_\. ]', '_', playlist_title)
                            
                            zip_filename = os.path.join(output_path, f"{playlist_title}_audio.zip")
                            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                                # Download each video in playlist
                                for video_url in p.video_urls:
                                    try:
                                        v = pytube.YouTube(video_url, on_progress_callback=self._pytube_progress_callback(progress_hook))
                                        
                                        # Get audio stream
                                        stream = v.streams.filter(only_audio=True).first()
                                        
                                        if stream:
                                            file_path = stream.download(output_path=playlist_temp_dir)
                                            
                                            # Convert to mp3 if ffmpeg is available
                                            if self.ffmpeg_available:
                                                base, _ = os.path.splitext(file_path)
                                                mp3_file = f"{base}.mp3"
                                                try:
                                                    subprocess.run([
                                                        'ffmpeg', '-i', file_path, '-vn', 
                                                        '-ar', '44100', '-ac', '2', '-b:a', '192k', 
                                                        mp3_file
                                                    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                                    os.remove(file_path)  # Remove original
                                                    file_path = mp3_file
                                                except Exception as conv_error:
                                                    logger.warning(f"Error converting to mp3: {str(conv_error)}")
                                            
                                            zipf.write(file_path, os.path.basename(file_path))
                                            os.remove(file_path)  # Clean up after adding to zip
                                    except Exception as video_error:
                                        logger.warning(f"Error downloading playlist audio: {str(video_error)}")
                                        continue
                            
                            # Clean up temporary playlist directory
                            shutil.rmtree(playlist_temp_dir)
                            audio_file = zip_filename
                        else:
                            # Single video audio download with pytube
                            v = pytube.YouTube(url, on_progress_callback=self._pytube_progress_callback(progress_hook))
                            
                            # Get audio stream
                            stream = v.streams.filter(only_audio=True).first()
                            
                            if stream:
                                audio_file = stream.download(output_path=output_path)
                                
                                # Convert to mp3 if ffmpeg is available
                                if self.ffmpeg_available:
                                    base, _ = os.path.splitext(audio_file)
                                    mp3_file = f"{base}.mp3"
                                    try:
                                        subprocess.run([
                                            'ffmpeg', '-i', audio_file, '-vn', 
                                            '-ar', '44100', '-ac', '2', '-b:a', '192k', 
                                            mp3_file
                                        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                        os.remove(audio_file)  # Remove original
                                        audio_file = mp3_file
                                    except Exception as conv_error:
                                        logger.warning(f"Error converting to mp3: {str(conv_error)}")
                                
                        # If we got here, pytube fallback worked
                        if audio_file:
                            break
                    
                    except Exception as pytube_error:
                        logger.error(f"Pytube fallback also failed: {str(pytube_error)}")
                        # All methods failed, will raise error after loop
                
                # Wait before retrying
                if attempt < self.RETRY_COUNT - 1:
                    sleep_time = self.RETRY_DELAY * (attempt + 1)  # Progressive backoff
                    logger.info(f"Waiting {sleep_time} seconds before retry...")
                    time.sleep(sleep_time)
        
        if not audio_file or not os.path.exists(audio_file):
            raise ValueError("Failed to download audio after multiple attempts. The video may be unavailable or restricted.")
        
        return audio_file
    
    def _pytube_progress_callback(self, progress_hook):
        """Create a progress callback for pytube that mimics yt-dlp's progress hook format"""
        if not progress_hook:
            return None
        
        total_size = [0]  # Use list to store mutable state
        
        def callback(stream, chunk, bytes_remaining):
            if total_size[0] == 0:
                total_size[0] = stream.filesize
            
            bytes_downloaded = total_size[0] - bytes_remaining
            
            progress_hook({
                'status': 'downloading',
                'downloaded_bytes': bytes_downloaded,
                'total_bytes': total_size[0],
                'filename': stream.default_filename
            })
        
        return callback
