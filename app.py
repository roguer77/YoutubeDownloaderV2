import os
import logging
import tempfile
import time
import threading
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import urllib.parse

# Import our modules
from downloader import YoutubeDownloader
from cache_manager import CacheManager
from models import db, Download, Statistics

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "youtube_downloader_secret")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
logger.debug(f"Database URL configured: {database_url is not None}")

# Initialize the database
db.init_app(app)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()
    logger.debug("Database tables created")

# Initialize the downloader and cache manager
downloader = YoutubeDownloader()
cache_manager = CacheManager(max_size=50)  # Store info for up to 50 videos

# Create a temporary directory for downloads
TEMP_DIR = tempfile.mkdtemp()
logger.debug(f"Created temporary directory at {TEMP_DIR}")

# Track download progress
download_progress = {}
downloads_lock = threading.Lock()

@app.route('/')
def index():
    """Main page with the video download form"""
    # Record site visit for statistics
    Statistics.record_visit()
    return render_template('index.html')
    
@app.route('/faq')
def faq():
    """Frequently Asked Questions page"""
    return render_template('faq.html', 
                          title='YouTube Downloader FAQ - Answers to Common Questions About Downloading Videos',
                          description='Find answers to frequently asked questions about downloading YouTube videos and converting videos to MP3 using our free online tool.')

@app.route('/video_info', methods=['POST'])
def get_video_info():
    """Get information about a YouTube video"""
    url = request.form.get('url', '')
    
    if not url:
        return jsonify({'error': 'Please enter a valid YouTube URL'}), 400
    
    try:
        # Check if this URL is in cache
        video_info = cache_manager.get_cache(url)
        
        if not video_info:
            # Not in cache, get the info
            video_info = downloader.get_video_info(url)
            cache_manager.add_to_cache(url, video_info)
        
        return jsonify(video_info)
    
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    """Download a YouTube video or audio"""
    url = request.form.get('url', '')
    format_id = request.form.get('format', 'best')
    download_type = request.form.get('type', 'video')
    playlist = request.form.get('playlist', 'false') == 'true'
    video_title = request.form.get('title', 'Unknown Video')
    
    if not url:
        flash('Please enter a valid YouTube URL', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Generate a unique ID for this download
        download_id = str(int(time.time() * 1000))
        with downloads_lock:
            download_progress[download_id] = {
                'progress': 0,
                'status': 'starting',
                'filename': None,
                'db_id': None,  # Will store database record ID
                'start_time': time.time()  # Track when download started
            }
        
        # Record download in database
        try:
            # Get client IP (we'll anonymize it for privacy)
            ip_address = request.remote_addr
            if ip_address:
                # Anonymize IP by removing last octet
                ip_parts = ip_address.split('.')
                if len(ip_parts) == 4:  # IPv4
                    ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0"
                else:
                    ip_address = "0.0.0.0"  # Fallback
            
            # Create download record
            download_record = Download.add_download(
                url=url,
                video_title=video_title,
                format_type=download_type,
                quality=format_id,
                status="started",
                ip_address=ip_address
            )
            
            # Store database ID in progress tracker
            with downloads_lock:
                download_progress[download_id]['db_id'] = download_record.id
                
            # Record download in statistics
            Statistics.record_download(download_type)
            
        except Exception as db_error:
            logger.error(f"Error recording download in database: {str(db_error)}")
            # Continue with download even if database recording fails
        
        # Start download in background thread
        download_thread = threading.Thread(
            target=process_download,
            args=(download_id, url, format_id, download_type, playlist)
        )
        download_thread.daemon = True
        download_thread.start()
        
        return jsonify({
            'download_id': download_id,
            'message': 'Download started'
        })
    
    except Exception as e:
        logger.error(f"Error starting download: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_download(download_id, url, format_id, download_type, playlist):
    """Process the download in a background thread"""
    try:
        with downloads_lock:
            download_progress[download_id]['status'] = 'downloading'
        
        # Define progress callback function
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total > 0:
                        percent = downloaded / total * 100
                    else:
                        percent = 0
                    
                    with downloads_lock:
                        download_progress[download_id]['progress'] = percent
                except Exception as e:
                    logger.error(f"Error updating progress: {str(e)}")
            
            elif d['status'] == 'finished':
                with downloads_lock:
                    download_progress[download_id]['status'] = 'processing'
        
        # Perform the download
        if download_type == 'audio':
            filename = downloader.download_audio(
                url, 
                output_path=TEMP_DIR, 
                progress_hook=progress_hook,
                playlist=playlist
            )
        else:  # video
            filename = downloader.download_video(
                url, 
                format_id=format_id, 
                output_path=TEMP_DIR, 
                progress_hook=progress_hook,
                playlist=playlist
            )
        
        # Update download status
        with downloads_lock:
            download_progress[download_id]['status'] = 'complete'
            download_progress[download_id]['filename'] = filename
            
            # Update database record if we have one
            db_id = download_progress[download_id].get('db_id')
            if db_id:
                try:
                    # Get file size if available
                    file_size = os.path.getsize(filename) if os.path.exists(filename) else None
                    
                    # Calculate download time (estimate)
                    start_time = download_progress[download_id].get('start_time', time.time() - 30)
                    download_time = time.time() - start_time
                    
                    # Update record in database
                    Download.update_status(
                        download_id=db_id,
                        status="completed",
                        file_size=file_size,
                        download_time=download_time
                    )
                except Exception as db_error:
                    logger.error(f"Error updating download record: {str(db_error)}")
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        with downloads_lock:
            download_progress[download_id]['status'] = 'error'
            download_progress[download_id]['error'] = str(e)
            
            # Update database record if we have one
            db_id = download_progress[download_id].get('db_id')
            if db_id:
                try:
                    # Update record in database
                    Download.update_status(
                        download_id=db_id,
                        status="failed"
                    )
                except Exception as db_error:
                    logger.error(f"Error updating download record: {str(db_error)}")

@app.route('/download_status/<download_id>', methods=['GET'])
def check_download_status(download_id):
    """Check the status of a download"""
    with downloads_lock:
        if download_id in download_progress:
            status = download_progress[download_id].copy()
            # If download is complete, include file download URL
            if status['status'] == 'complete' and status['filename']:
                status['download_url'] = url_for('get_file', download_id=download_id)
            return jsonify(status)
        else:
            return jsonify({'error': 'Download not found'}), 404

@app.route('/get_file/<download_id>', methods=['GET'])
def get_file(download_id):
    """Download the completed file"""
    with downloads_lock:
        if download_id in download_progress and download_progress[download_id]['status'] == 'complete':
            filename = download_progress[download_id]['filename']
            if filename and os.path.exists(filename):
                basename = os.path.basename(filename)
                
                # After download is complete, mark for cleanup
                def cleanup_file():
                    # Wait a bit to ensure file is fully downloaded
                    time.sleep(300)  # 5 minutes
                    try:
                        if os.path.exists(filename):
                            os.remove(filename)
                            logger.debug(f"Removed temporary file: {filename}")
                        with downloads_lock:
                            if download_id in download_progress:
                                del download_progress[download_id]
                    except Exception as e:
                        logger.error(f"Error cleaning up file: {str(e)}")
                
                cleanup_thread = threading.Thread(target=cleanup_file)
                cleanup_thread.daemon = True
                cleanup_thread.start()
                
                return send_file(
                    filename,
                    as_attachment=True,
                    download_name=basename
                )
    
    return jsonify({'error': 'File not found or download not complete'}), 404

@app.route('/error')
def error_page():
    """Display error page"""
    error = request.args.get('error', 'An unknown error occurred')
    return render_template('error.html', error=error)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {str(e)}")
    return render_template('error.html', error='Server error occurred'), 500

@app.route('/robots.txt')
def robots():
    """Serve robots.txt file"""
    return send_from_directory('static', 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml file"""
    return send_from_directory('static', 'sitemap.xml')

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard with download statistics"""
    # This should have proper authentication in production
    
    # Get overall statistics
    current_date = datetime.datetime.utcnow().date()
    last_week = current_date - datetime.timedelta(days=7)
    
    # Get all stats data
    all_stats = Statistics.query.all()
    
    # Calculate total statistics
    total_visits = sum(stat.visits for stat in all_stats)
    total_downloads = sum(stat.downloads for stat in all_stats)
    video_downloads = sum(stat.video_downloads for stat in all_stats)
    audio_downloads = sum(stat.audio_downloads for stat in all_stats)
    
    # Prepare chart data for last 7 days
    last_7_days = []
    for i in range(6, -1, -1):
        day = current_date - datetime.timedelta(days=i)
        last_7_days.append(day)
    
    # Format dates and get data for chart
    date_labels = [day.strftime('%b %d') for day in last_7_days]
    visits_data = []
    downloads_data = []
    
    for day in last_7_days:
        stat = Statistics.query.filter_by(date=day).first()
        visits_data.append(stat.visits if stat else 0)
        downloads_data.append(stat.downloads if stat else 0)
    
    # Get popular downloads (using raw SQL for grouping and counting)
    from sqlalchemy import text
    popular_downloads = db.session.execute(
        text("""
        SELECT video_title, format_type, quality, COUNT(*) as count
        FROM download
        WHERE status = 'completed'
        GROUP BY video_title, format_type, quality
        ORDER BY count DESC
        LIMIT 10
        """)
    ).fetchall()
    
    # Get recent downloads
    recent_downloads = Download.query.order_by(Download.created_at.desc()).limit(20).all()
    
    return render_template(
        'admin.html',
        stats={
            'total_visits': total_visits,
            'total_downloads': total_downloads,
            'video_downloads': video_downloads,
            'audio_downloads': audio_downloads
        },
        chart_data={
            'labels': date_labels,
            'visits': visits_data,
            'downloads': downloads_data
        },
        popular_downloads=popular_downloads,
        recent_downloads=recent_downloads
    )

# SEO-optimized metadata for page titles and descriptions
@app.context_processor
def inject_seo_metadata():
    """Inject SEO metadata for templates"""
    return {
        'default_title': 'YouTube Downloader - Download Videos and Audio in High Quality | Free Online Tool',
        'default_description': 'Free YouTube video downloader that allows you to download YouTube videos and audio in multiple formats and qualities. Convert YouTube videos to MP3, MP4, and more.',
        'current_year': time.strftime("%Y")
    }

# Cleanup temporary files before exit
def cleanup_temp_files():
    logger.debug("Cleaning up temporary files")
    import shutil
    try:
        shutil.rmtree(TEMP_DIR)
    except Exception as e:
        logger.error(f"Error cleaning up temporary directory: {str(e)}")

import atexit
atexit.register(cleanup_temp_files)
