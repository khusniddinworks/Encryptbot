import requests
import time
import threading
import logging

logger = logging.getLogger(__name__)

def ping_self(url, interval_minutes=10):
    """
    Pings the given URL every interval_minutes to keep the service awake.
    """
    if not url:
        logger.warning("RENDER_EXTERNAL_URL not set. Self-ping disabled.")
        return

    def run():
        logger.info(f"Self-ping thread started for {url} every {interval_minutes}m")
        while True:
            try:
                # Ping the health check endpoint
                response = requests.get(url)
                logger.info(f"Self-ping status: {response.status_code}")
            except Exception as e:
                logger.error(f"Self-ping failed: {e}")
            
            # Wait for the next interval
            time.sleep(interval_minutes * 60)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
