from loader import bot, logger
from config import DOWNLOADS_DIR
from utils.file_cleaner import FileCleaner, start_cleanup_scheduler
from utils.commands import set_default_commands
from utils.keep_alive import ping_self
import handlers.user
import handlers.admin
import handlers.encryption
import os
import threading
from flask import Flask

# Keep-alive server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive! 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    logger.info("🚀 Starting Bot...")
    
    # Set Commands
    set_default_commands()

    # Start Keep-Alive Server (Flask)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start Self-Ping (to avoid Render sleep)
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if external_url:
        ping_self(external_url, interval_minutes=10)
    
    # Start File Cleaner
    file_cleaner = FileCleaner(downloads_dir=DOWNLOADS_DIR, max_age_hours=24)
    start_cleanup_scheduler(file_cleaner, interval_hours=1)
    
    # Start Polling
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
