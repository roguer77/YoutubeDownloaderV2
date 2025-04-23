from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Download(db.Model):
    """Model to track download history"""
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    video_title = db.Column(db.String(255))
    format_type = db.Column(db.String(50))  # video or audio
    quality = db.Column(db.String(50))      # e.g., 1080p, 720p, etc.
    file_size = db.Column(db.Integer)       # Size in bytes
    download_time = db.Column(db.Float)     # Time in seconds
    status = db.Column(db.String(50))       # completed, failed, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))   # To track unique users (anonymized)
    
    def __repr__(self):
        return f'<Download {self.id}: {self.video_title}>'
    
    @staticmethod
    def add_download(url, video_title, format_type, quality, file_size=None, 
                    download_time=None, status="started", ip_address=None):
        """Create a new download record"""
        download = Download(
            url=url,
            video_title=video_title,
            format_type=format_type,
            quality=quality,
            file_size=file_size,
            download_time=download_time,
            status=status,
            ip_address=ip_address
        )
        db.session.add(download)
        db.session.commit()
        return download
    
    @staticmethod
    def update_status(download_id, status, file_size=None, download_time=None):
        """Update an existing download record with completion info"""
        download = Download.query.get(download_id)
        if download:
            download.status = status
            if file_size:
                download.file_size = file_size
            if download_time:
                download.download_time = download_time
            db.session.commit()
            return download
        return None
    
    @staticmethod
    def get_popular_downloads(limit=10):
        """Get most popular downloaded videos"""
        return Download.query.filter_by(status="completed").group_by(
            Download.video_title).order_by(
            db.func.count(Download.video_title).desc()).limit(limit).all()

class Statistics(db.Model):
    """Model to track website usage statistics"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, unique=True)
    visits = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    video_downloads = db.Column(db.Integer, default=0)
    audio_downloads = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Statistics {self.date}: {self.visits} visits, {self.downloads} downloads>'
    
    @staticmethod
    def record_visit():
        """Increment visit counter for today"""
        today = datetime.utcnow().date()
        stats = Statistics.query.filter_by(date=today).first()
        
        if not stats:
            stats = Statistics(date=today, visits=1)
            db.session.add(stats)
        else:
            stats.visits += 1
        
        db.session.commit()
        return stats
    
    @staticmethod
    def record_download(format_type):
        """Increment download counter for today"""
        today = datetime.utcnow().date()
        stats = Statistics.query.filter_by(date=today).first()
        
        if not stats:
            stats = Statistics(
                date=today, 
                downloads=1,
                video_downloads=1 if format_type == 'video' else 0,
                audio_downloads=1 if format_type == 'audio' else 0
            )
            db.session.add(stats)
        else:
            stats.downloads += 1
            if format_type == 'video':
                stats.video_downloads += 1
            elif format_type == 'audio':
                stats.audio_downloads += 1
        
        db.session.commit()
        return stats