
# YouTube Downloader Application

A Flask-based web application that allows users to download YouTube videos and audio with various quality options.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)

## Features
- Download YouTube videos in multiple quality formats
- Extract audio from YouTube videos
- Support for playlist downloads
- Progress tracking for downloads
- Automatic file cleanup
- Mobile-responsive UI
- Anti-bot detection measures

## Prerequisites
- Python 3.x
- Flask web framework
- yt-dlp library
- ffmpeg for audio processing

## Installation

1. Create a new Repl and choose "Python" as the template

2. Install required packages:
```bash
pip install flask yt-dlp pytube ffmpeg-python requests
```

3. Project structure should look like:
```
├── static/
│   ├── css/
│   │   ├── custom.css
│   │   └── style.css
│   └── js/
│       └── script.js
├── templates/
│   ├── error.html
│   ├── index.html
│   └── layout.html
├── app.py
├── downloader.py
├── cache_manager.py
├── main.py
```

## Configuration

### Basic Setup
1. Set up Flask application in `main.py`:
```python
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

2. Configure logging in `app.py`:
```python
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

### Environment Variables
- `YOUTUBE_API_KEY`: (Optional) For enhanced video information
- `SESSION_SECRET`: For Flask session security

## Project Structure Explanation

### Core Components

1. `app.py`: Main Flask application
   - Routes handling
   - Request processing
   - Error handling
   - Session management

2. `downloader.py`: Download functionality
   - Video/audio downloading
   - Progress tracking
   - Format handling
   - Anti-bot measures

3. `cache_manager.py`: Caching system
   - Video info caching
   - Cache cleanup
   - Memory management

### Frontend Structure

1. Templates:
   - `layout.html`: Base template
   - `index.html`: Main download page
   - `error.html`: Error display

2. Static Files:
   - `custom.css`: Custom styling
   - `style.css`: Base styling
   - `script.js`: Frontend functionality

## Usage

### Starting the Application

1. Click the "Run" button in Replit
2. The application will start on port 5000

### Basic Operations

1. Video Download:
   - Paste YouTube URL
   - Select quality
   - Click download

2. Audio Download:
   - Paste URL
   - Choose audio format
   - Download

3. Playlist Download:
   - Paste playlist URL
   - Select quality
   - Download as ZIP

## Error Handling

Common errors and solutions:

1. Bot Detection:
```python
# Handled in downloader.py with retry mechanism
if "sign in" in error_msg or "not a bot" in error_msg:
    # Use alternative download method
    fallback_opts = ydl_opts.copy()
    fallback_opts['format'] = 'best'
```

2. Rate Limiting:
```python
# Implemented in downloader.py
RATE_LIMIT_DELAY = 2
RETRY_COUNT = 3
RETRY_DELAY = 5
```

## Troubleshooting

1. Download Fails
   - Check URL validity
   - Verify video availability
   - Check for rate limiting
   - Clear cache and retry

2. Quality Issues
   - Verify available formats
   - Check network connection
   - Try alternative quality

3. Audio Extraction Problems
   - Verify ffmpeg installation
   - Check file permissions
   - Try alternative format

## Security Considerations

1. File Safety:
   - Automatic file cleanup
   - Secure filename handling
   - Temporary file management

2. Rate Limiting:
   - Request delays
   - Progressive backoff
   - Multiple retry attempts

## Maintenance

1. Regular Tasks:
   - Clear temporary files
   - Update dependencies
   - Monitor error logs

2. Cache Management:
   - Set cache limits
   - Implement cleanup
   - Monitor memory usage

Remember to regularly check for updates to dependencies, especially yt-dlp, as YouTube's interface may change requiring updates to the download functionality.
