// YouTube Downloader Frontend Functionality

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const youtubeForm = document.getElementById('youtube-form');
    const youtubeUrlInput = document.getElementById('youtube-url');
    const videoInfoContainer = document.getElementById('video-info');
    const videoLoader = document.getElementById('video-loader');
    const errorContainer = document.getElementById('error-container');
    const videoDetailsContainer = document.getElementById('video-details');
    const thumbnailElement = document.getElementById('video-thumbnail');
    const videoTitleElement = document.getElementById('video-title');
    const videoDurationElement = document.getElementById('video-duration');
    const videoUploaderElement = document.getElementById('video-uploader');
    const videoViewsElement = document.getElementById('video-views');
    const videoFormatsContainer = document.getElementById('video-formats');
    const audioFormatsContainer = document.getElementById('audio-formats');
    const downloadButton = document.getElementById('download-button');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const downloadCompleteAlert = document.getElementById('download-complete');
    const downloadLink = document.getElementById('download-link');
    const videoTabButton = document.getElementById('video-tab-button');
    const audioTabButton = document.getElementById('audio-tab-button');
    const playlistItemsContainer = document.getElementById('playlist-items');
    const playlistInfoContainer = document.getElementById('playlist-info');
    
    // Global variables
    let currentVideoInfo = null;
    let selectedFormat = null;
    let downloadType = 'video'; // Default download type
    let isDownloading = false;
    let downloadCheckInterval = null;
    let isPlaylist = false;
    
    // Initialize tooltips if Bootstrap is loaded
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Event Listeners
    if (youtubeForm) {
        youtubeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            getVideoInfo();
        });
    }
    
    if (videoTabButton) {
        videoTabButton.addEventListener('click', function() {
            downloadType = 'video';
            updateDownloadButton();
        });
    }
    
    if (audioTabButton) {
        audioTabButton.addEventListener('click', function() {
            downloadType = 'audio';
            updateDownloadButton();
        });
    }
    
    if (downloadButton) {
        downloadButton.addEventListener('click', function() {
            if (!isDownloading && selectedFormat) {
                startDownload();
            }
        });
    }
    
    // Functions
    function getVideoInfo() {
        const youtubeUrl = youtubeUrlInput.value.trim();
        
        if (!youtubeUrl) {
            showError('Please enter a YouTube URL');
            return;
        }
        
        // Reset UI state
        resetUI();
        
        // Show loader
        videoLoader.style.display = 'block';
        
        // Fetch video info from server
        const formData = new FormData();
        formData.append('url', youtubeUrl);
        
        fetch('/video_info', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Error fetching video information');
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loader
            videoLoader.style.display = 'none';
            
            // Store video info
            currentVideoInfo = data;
            isPlaylist = data.is_playlist;
            
            // Display video information
            displayVideoInfo(data);
        })
        .catch(error => {
            videoLoader.style.display = 'none';
            showError(error.message);
        });
    }
    
    function displayVideoInfo(videoInfo) {
        // Show video info container
        videoInfoContainer.style.display = 'block';
        
        if (videoInfo.is_playlist) {
            // Display playlist information
            displayPlaylistInfo(videoInfo);
        } else {
            // Display single video information
            displaySingleVideoInfo(videoInfo);
        }
        
        // Auto-select the first video format
        if (videoInfo.formats && videoInfo.formats.length > 0) {
            selectedFormat = videoInfo.formats[0].format_id;
            updateFormatSelection();
        }
        
        // Update download button state
        updateDownloadButton();
        
        // Make sure the formats tab is active by default
        if (videoTabButton && typeof bootstrap !== 'undefined' && bootstrap.Tab) {
            const videoTab = new bootstrap.Tab(videoTabButton);
            videoTab.show();
        }
        
        // Scroll to the format selection area to improve UX
        setTimeout(() => {
            videoInfoContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            
            // Also highlight the format selection area with a subtle animation
            const formatTabsContent = document.getElementById('formatTabsContent');
            if (formatTabsContent) {
                formatTabsContent.classList.add('highlight-pulse');
                setTimeout(() => {
                    formatTabsContent.classList.remove('highlight-pulse');
                }, 1500);
            }
        }, 100);
    }
    
    function displaySingleVideoInfo(videoInfo) {
        // Hide playlist container if visible
        if (playlistInfoContainer) {
            playlistInfoContainer.style.display = 'none';
        }
        
        // Show video details container
        videoDetailsContainer.style.display = 'block';
        
        // Set thumbnail with a fallback
        if (thumbnailElement) {
            if (videoInfo.thumbnail) {
                thumbnailElement.src = videoInfo.thumbnail;
                thumbnailElement.style.display = 'block';
            } else {
                thumbnailElement.style.display = 'none';
            }
        }
        
        // Set video title
        if (videoTitleElement) {
            videoTitleElement.textContent = videoInfo.title || 'Unknown Title';
        }
        
        // Set video duration
        if (videoDurationElement) {
            const duration = videoInfo.duration ? formatDuration(videoInfo.duration) : 'Unknown';
            videoDurationElement.textContent = duration;
        }
        
        // Set video uploader
        if (videoUploaderElement) {
            videoUploaderElement.textContent = videoInfo.uploader || 'Unknown Uploader';
        }
        
        // Set video views
        if (videoViewsElement) {
            const views = videoInfo.view_count ? formatViews(videoInfo.view_count) : 'Unknown';
            videoViewsElement.textContent = views;
        }
        
        // Display video formats
        if (videoFormatsContainer) {
            videoFormatsContainer.innerHTML = '';
            
            if (videoInfo.formats && videoInfo.formats.length > 0) {
                videoInfo.formats.forEach(format => {
                    const formatElement = document.createElement('div');
                    formatElement.className = 'form-check format-select';
                    formatElement.innerHTML = `
                        <input class="form-check-input" type="radio" name="videoFormat" id="format_${format.format_id}" value="${format.format_id}">
                        <label class="form-check-label" for="format_${format.format_id}">
                            ${format.format_note || format.format_id}
                        </label>
                    `;
                    
                    formatElement.querySelector('input').addEventListener('change', function() {
                        selectedFormat = this.value;
                        updateFormatSelection();
                        updateDownloadButton();
                    });
                    
                    videoFormatsContainer.appendChild(formatElement);
                });
                
                // Select the first format by default
                const firstInput = videoFormatsContainer.querySelector('input');
                if (firstInput) {
                    firstInput.checked = true;
                    selectedFormat = firstInput.value;
                }
            } else {
                videoFormatsContainer.innerHTML = '<p class="text-muted">No video formats available</p>';
            }
        }
        
        // Display audio formats
        if (audioFormatsContainer) {
            audioFormatsContainer.innerHTML = '';
            
            if (videoInfo.audio_formats && videoInfo.audio_formats.length > 0) {
                videoInfo.audio_formats.forEach(format => {
                    const formatElement = document.createElement('div');
                    formatElement.className = 'form-check format-select';
                    formatElement.innerHTML = `
                        <input class="form-check-input" type="radio" name="audioFormat" id="audio_${format.format_id}" value="${format.format_id}">
                        <label class="form-check-label" for="audio_${format.format_id}">
                            ${format.format_note || format.format_id}
                        </label>
                    `;
                    
                    formatElement.querySelector('input').addEventListener('change', function() {
                        selectedFormat = this.value;
                        updateFormatSelection();
                        updateDownloadButton();
                    });
                    
                    audioFormatsContainer.appendChild(formatElement);
                });
                
                // Don't select by default, let the user choose
            } else {
                audioFormatsContainer.innerHTML = '<p class="text-muted">No audio formats available</p>';
            }
        }
    }
    
    function displayPlaylistInfo(playlistInfo) {
        // Hide single video details if visible
        if (videoDetailsContainer) {
            videoDetailsContainer.style.display = 'none';
        }
        
        // Show playlist info container
        if (playlistInfoContainer) {
            playlistInfoContainer.style.display = 'block';
            
            // Set playlist title
            const playlistTitleElement = playlistInfoContainer.querySelector('#playlist-title');
            if (playlistTitleElement) {
                playlistTitleElement.textContent = playlistInfo.title || 'YouTube Playlist';
            }
            
            // Set playlist count
            const playlistCountElement = playlistInfoContainer.querySelector('#playlist-count');
            if (playlistCountElement) {
                playlistCountElement.textContent = playlistInfo.playlist_count || 'Unknown';
            }
            
            // Display playlist items
            if (playlistItemsContainer) {
                playlistItemsContainer.innerHTML = '';
                
                if (playlistInfo.entries && playlistInfo.entries.length > 0) {
                    playlistInfo.entries.forEach((item, index) => {
                        const itemElement = document.createElement('div');
                        itemElement.className = 'playlist-item';
                        itemElement.innerHTML = `
                            <div class="d-flex align-items-center">
                                <span class="me-2">${index + 1}.</span>
                                <div>
                                    <div class="fw-bold">${item.title || 'Unknown Title'}</div>
                                    <small class="text-muted">${formatDuration(item.duration || 0)}</small>
                                </div>
                            </div>
                        `;
                        
                        playlistItemsContainer.appendChild(itemElement);
                    });
                    
                    // Add info about more videos if not all are shown
                    if (playlistInfo.playlist_count > playlistInfo.entries.length) {
                        const moreElement = document.createElement('div');
                        moreElement.className = 'playlist-item text-center text-muted';
                        moreElement.textContent = `And ${playlistInfo.playlist_count - playlistInfo.entries.length} more videos...`;
                        playlistItemsContainer.appendChild(moreElement);
                    }
                } else {
                    playlistItemsContainer.innerHTML = '<p class="text-muted">No playlist items available</p>';
                }
            }
            
            // Display playlist formats
            if (videoFormatsContainer) {
                videoFormatsContainer.innerHTML = '';
                
                if (playlistInfo.formats && playlistInfo.formats.length > 0) {
                    playlistInfo.formats.forEach(format => {
                        const formatElement = document.createElement('div');
                        formatElement.className = 'form-check format-select';
                        formatElement.innerHTML = `
                            <input class="form-check-input" type="radio" name="videoFormat" id="format_${format.format_id}" value="${format.format_id}">
                            <label class="form-check-label" for="format_${format.format_id}">
                                ${format.format_note || format.format_id}
                            </label>
                        `;
                        
                        formatElement.querySelector('input').addEventListener('change', function() {
                            selectedFormat = this.value;
                            updateFormatSelection();
                            updateDownloadButton();
                        });
                        
                        videoFormatsContainer.appendChild(formatElement);
                    });
                    
                    // Select the first format by default
                    const firstInput = videoFormatsContainer.querySelector('input');
                    if (firstInput) {
                        firstInput.checked = true;
                        selectedFormat = firstInput.value;
                    }
                } else {
                    videoFormatsContainer.innerHTML = '<p class="text-muted">No video formats available</p>';
                }
            }
            
            // Display audio formats
            if (audioFormatsContainer) {
                audioFormatsContainer.innerHTML = '';
                
                if (playlistInfo.audio_formats && playlistInfo.audio_formats.length > 0) {
                    playlistInfo.audio_formats.forEach(format => {
                        const formatElement = document.createElement('div');
                        formatElement.className = 'form-check format-select';
                        formatElement.innerHTML = `
                            <input class="form-check-input" type="radio" name="audioFormat" id="audio_${format.format_id}" value="${format.format_id}">
                            <label class="form-check-label" for="audio_${format.format_id}">
                                ${format.format_note || format.format_id}
                            </label>
                        `;
                        
                        formatElement.querySelector('input').addEventListener('change', function() {
                            selectedFormat = this.value;
                            updateFormatSelection();
                            updateDownloadButton();
                        });
                        
                        audioFormatsContainer.appendChild(formatElement);
                    });
                } else {
                    audioFormatsContainer.innerHTML = '<p class="text-muted">No audio formats available</p>';
                }
            }
        }
    }
    
    function startDownload() {
        if (!currentVideoInfo || !selectedFormat) {
            showError('Please select a format to download');
            return;
        }
        
        // Update UI state
        isDownloading = true;
        updateDownloadButton();
        
        // Show progress container
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', '0');
        progressText.textContent = 'Starting download...';
        
        // Hide any previous download complete alert
        downloadCompleteAlert.style.display = 'none';
        
        // Prepare form data
        const formData = new FormData();
        formData.append('url', youtubeUrlInput.value.trim());
        formData.append('format', selectedFormat);
        formData.append('type', downloadType);
        formData.append('playlist', isPlaylist.toString());
        
        // Start download request
        fetch('/download', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Error starting download');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.download_id) {
                // Start checking download progress
                checkDownloadProgress(data.download_id);
            } else {
                throw new Error('No download ID received from server');
            }
        })
        .catch(error => {
            isDownloading = false;
            updateDownloadButton();
            progressContainer.style.display = 'none';
            showError(error.message);
        });
    }
    
    function checkDownloadProgress(downloadId) {
        // Clear any existing interval
        if (downloadCheckInterval) {
            clearInterval(downloadCheckInterval);
        }
        
        // Check progress every 1 second
        downloadCheckInterval = setInterval(() => {
            fetch(`/download_status/${downloadId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to get download status');
                    }
                    return response.json();
                })
                .then(status => {
                    updateProgressUI(status);
                    
                    // If download is complete or failed, stop checking
                    if (status.status === 'complete' || status.status === 'error') {
                        clearInterval(downloadCheckInterval);
                        downloadCheckInterval = null;
                        isDownloading = false;
                        updateDownloadButton();
                        
                        if (status.status === 'complete' && status.download_url) {
                            // Show download complete message with link
                            downloadCompleteAlert.style.display = 'block';
                            downloadLink.href = status.download_url;
                            downloadLink.download = status.filename ? status.filename.split('/').pop() : 'youtube_download';
                        }
                        
                        if (status.status === 'error') {
                            showError(`Download failed: ${status.error || 'Unknown error'}`);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking download status:', error);
                });
        }, 1000);
    }
    
    function updateProgressUI(status) {
        if (status.status === 'starting') {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', '0');
            progressText.textContent = 'Starting download...';
        } else if (status.status === 'downloading') {
            const progress = Math.round(status.progress);
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
            progressText.textContent = `Downloading: ${progress}%`;
        } else if (status.status === 'processing') {
            progressBar.style.width = '100%';
            progressBar.setAttribute('aria-valuenow', '100');
            progressText.textContent = 'Processing file...';
        } else if (status.status === 'complete') {
            progressBar.style.width = '100%';
            progressBar.setAttribute('aria-valuenow', '100');
            progressText.textContent = 'Download complete!';
        } else if (status.status === 'error') {
            progressBar.style.width = '100%';
            progressBar.classList.remove('bg-success');
            progressBar.classList.add('bg-danger');
            progressText.textContent = `Error: ${status.error || 'Unknown error'}`;
        }
    }
    
    function updateFormatSelection() {
        // Update the active class for video formats
        document.querySelectorAll('#video-formats .format-select').forEach(el => {
            const input = el.querySelector('input');
            if (input.value === selectedFormat && input.checked) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
        
        // Update the active class for audio formats
        document.querySelectorAll('#audio-formats .format-select').forEach(el => {
            const input = el.querySelector('input');
            if (input.value === selectedFormat && input.checked) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
    }
    
    function updateDownloadButton() {
        if (downloadButton) {
            if (isDownloading) {
                downloadButton.disabled = true;
                downloadButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Downloading...';
            } else if (!selectedFormat) {
                downloadButton.disabled = true;
                downloadButton.textContent = 'Select a format';
            } else {
                downloadButton.disabled = false;
                
                // Set button text based on download type and playlist status
                let buttonText = 'Download';
                
                if (isPlaylist) {
                    buttonText += ' Playlist';
                }
                
                if (downloadType === 'audio') {
                    buttonText += ' Audio';
                } else {
                    buttonText += ' Video';
                }
                
                downloadButton.textContent = buttonText;
            }
        }
    }
    
    function showError(message) {
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    ${message}
                </div>
            `;
            errorContainer.style.display = 'block';
        } else {
            alert(message);
        }
    }
    
    function resetUI() {
        // Hide video info
        videoInfoContainer.style.display = 'none';
        
        // Hide video details
        if (videoDetailsContainer) {
            videoDetailsContainer.style.display = 'none';
        }
        
        // Hide playlist info
        if (playlistInfoContainer) {
            playlistInfoContainer.style.display = 'none';
        }
        
        // Hide error container
        if (errorContainer) {
            errorContainer.style.display = 'none';
        }
        
        // Hide progress container
        progressContainer.style.display = 'none';
        
        // Hide download complete alert
        downloadCompleteAlert.style.display = 'none';
        
        // Reset global variables
        selectedFormat = null;
        isDownloading = false;
        isPlaylist = false;
        
        // Clear any running interval
        if (downloadCheckInterval) {
            clearInterval(downloadCheckInterval);
            downloadCheckInterval = null;
        }
    }
    
    // Utility Functions
    function formatDuration(seconds) {
        if (!seconds) return '0:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        } else {
            return `${minutes}:${String(secs).padStart(2, '0')}`;
        }
    }
    
    function formatViews(views) {
        if (!views) return '0 views';
        
        if (views >= 1000000) {
            return `${(views / 1000000).toFixed(1)}M views`;
        } else if (views >= 1000) {
            return `${(views / 1000).toFixed(1)}K views`;
        } else {
            return `${views} views`;
        }
    }
});
