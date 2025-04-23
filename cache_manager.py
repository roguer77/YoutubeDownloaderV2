import time
import logging
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)

class CacheManager:
    """Cache manager for storing video information to reduce API calls"""
    
    def __init__(self, max_size=100, expiry_time=3600):  # Default 1 hour expiry
        """Initialize the cache with maximum size and expiry time"""
        self.cache = OrderedDict()  # Use OrderedDict for LRU functionality
        self.max_size = max_size
        self.expiry_time = expiry_time
        self.lock = threading.Lock()
        
        # Start a cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        self.cleanup_thread.start()
    
    def add_to_cache(self, key, value):
        """Add an item to the cache with the current timestamp"""
        with self.lock:
            # Remove oldest item if cache is full
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            
            # Add new item with timestamp
            self.cache[key] = {
                'value': value,
                'timestamp': time.time()
            }
            logger.debug(f"Added item to cache: {key}")
    
    def get_cache(self, key):
        """Get an item from cache if it exists and is not expired"""
        with self.lock:
            if key in self.cache:
                cache_item = self.cache[key]
                current_time = time.time()
                
                # Check if item is expired
                if current_time - cache_item['timestamp'] > self.expiry_time:
                    # Remove expired item
                    self.cache.pop(key)
                    logger.debug(f"Cache item expired: {key}")
                    return None
                
                # Move item to the end (most recently used)
                self.cache.move_to_end(key)
                logger.debug(f"Cache hit: {key}")
                return cache_item['value']
            
            logger.debug(f"Cache miss: {key}")
            return None
    
    def clear_cache(self):
        """Clear all items from cache"""
        with self.lock:
            self.cache.clear()
            logger.debug("Cache cleared")
    
    def remove_from_cache(self, key):
        """Remove a specific item from cache"""
        with self.lock:
            if key in self.cache:
                self.cache.pop(key)
                logger.debug(f"Removed item from cache: {key}")
                return True
            return False
    
    def _cleanup_expired(self):
        """Periodically clean up expired cache items"""
        while True:
            time.sleep(300)  # Check every 5 minutes
            
            with self.lock:
                current_time = time.time()
                # Create a list of keys to remove to avoid modifying during iteration
                keys_to_remove = []
                
                for key, cache_item in self.cache.items():
                    if current_time - cache_item['timestamp'] > self.expiry_time:
                        keys_to_remove.append(key)
                
                # Remove expired items
                for key in keys_to_remove:
                    self.cache.pop(key)
                
                if keys_to_remove:
                    logger.debug(f"Cleanup: removed {len(keys_to_remove)} expired cache items")
