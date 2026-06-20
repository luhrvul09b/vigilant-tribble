import os
import re
import time
import asyncio
import mimetypes
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Human readable bytes converter
def get_readable_size(size_in_bytes):
    if size_in_bytes is None or size_in_bytes == 0:
        return "0 B"
    index = 0
    while size_in_bytes >= 1024 and index < 4:
        size_in_bytes /= 1024
        index += 1
    return f"{size_in_bytes:.2f} {['B', 'KB', 'MB', 'GB', 'TB'][index]}"

# Custom File Reader for Live Upload Progress
class ProgressFileReader:
    def __init__(self, filename, tracker):
        self.file_obj = open(filename, "rb")
        self.tracker = tracker

    def read(self, size=-1):
        chunk = self.file_obj.read(size)
        self.tracker["uploaded"] += len(chunk)
        return chunk
        
    def seek(self, offset, whence=0):
        return self.file_obj.seek(offset, whence)
        
    def tell(self):
        return self.file_obj.tell()

    def close(self):
        self.file_obj.close()

    @property
    def name(self):
        return self.file_obj.name

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Advanced Downloader Bot**\n\nMujhe link bhejein, main live Download aur Upload progress ke sath file Telegram par bhej dunga!"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please ek valid HTTP/HTTPS direct link bhejein.")
        return

    status_message = await update.message.reply_text("⚡ **Server se connect ho raha hai...**")

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        filename = "downloaded_file.mp4"

    try:
        # ==========================================
        # 1. DOWNLOAD PHASE (Aria2c)
        # ==========================================
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        command = [
            "aria2c",
            "-x", "4",  # Hugging Face ke liye 4 safe hai (Block nahi hoga)
            "-s", "4",
            "--continue=true", # Error aane par resume karega
            f"--user-agent={user_agent}",
            "--max-tries=10",
            "--retry-wait=3",
            "--summary-interval=1",
            "--out", filename,
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        last_edit_time = time.time()

        while True:
            line_bytes = await process.stdout.readline()
            if not line_bytes:
                break
                
            line = line_bytes.decode('utf-8', errors='ignore')
            
            # Aria2 status fetch karna
            match = re.search(r'\[#\w+\s+([\d\w\.]+)/([\d\w\.]+)\(([\d%]+)\)\s+CN:\d+\s+DL:([\d\w\.]+)(?:.*)\]', line)
            
            if match:
                downloaded = match.group(1)   
                total_size = match.group(2)   
                percentage = match.group(3)   
                speed = match.group(4)        

                # Exactly 3 second update rule
                if time.time() - last_edit_time >= 3:
                    try:
                        pct_num = int(percentage.replace('%', ''))
                        bars = int(pct_num / 10)
                        progress_bar = "■" * bars + "□" * (10 - bars)
                    except:
                        progress_bar = "■■■■■■■■■■"

                    progress_text = (
                        f"📥 **Downloading (Live)...**\n\n"
                        f"📁 **File:** `{filename}`\n"
                        f"📊 **Progress:** `[{progress_bar}] {percentage}`\n"
                        f"⚙️ **Status:** `{downloaded} / {total_size}`\n"
                        f"⚡ **Speed:** `{speed}/s`"
                    )
                    try:
                        await status_message.edit_text(progress_text, parse_mode="Markdown")
                        last_edit_time = time.time()
                    except Exception:
                        pass

        await process.wait()

        if process.returncode != 0:
            raise Exception("Server ne link close kar di. Link check karein.")

        # ==========================================
        # 2. UPLOAD PHASE (Custom Tracker)
        # ==========================================
        await status_message.edit_text("📤 **Download mukammal! Upload shuru ho raha hai...**")
        
        total_size_bytes = os.path.getsize(filename)
        tracker = {"uploaded": 0, "total": total_size_bytes}
        
        # Upload Progress Update Task (Background me chalega)
        async def update_upload_progress():
            last_uploaded = 0
            last_time = time.time()
            
            while tracker["uploaded"] < tracker["total"]:
                await asyncio.sleep(3) # Har 3 sec update
                
                current_uploaded = tracker["uploaded"]
                current_time = time.time()
                
                if current_uploaded == last_uploaded:
                    continue
                    
                # Speed Calculation
                time_diff = current_time - last_time
                speed_bps = (current_uploaded - last_uploaded) / time_diff if time_diff > 0 else 0
                
                last_uploaded = current_uploaded
                last_time = current_time
                
                percentage = (current_uploaded / tracker["total"]) * 100
                pct_num = int(percentage)
                bars = pct_num // 10
                progress_bar = "■" * bars + "□" * (10 - bars)
                
                dl_str = get_readable_size(current_uploaded)
                tot_str = get_readable_size(tracker["total"])
                spd_str = get_readable_size(speed_bps)
                
                progress_text = (
                    f"📤 **Uploading to Telegram...**\n\n"
                    f"📁 **File:** `{filename}`\n"
                    f"📊 **Progress:** `[{progress_bar}] {percentage:.1f}%`\n"
                    f"⚙️ **Status:** `{dl_str} / {tot_str}`\n"
                    f"⚡ **Speed:** `{spd_str}/s`"
                )
                
                try:
                    await status_message.edit_text(progress_text, parse_mode="Markdown")
                except Exception:
                    pass

        # Tracker task ko start karein
        upload_task = asyncio.create_task(update_upload_progress())

        # File bhejne ka logic
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or ""

        with ProgressFileReader(filename, tracker) as file_to_send:
            if 'video' in mime_type:
                await update.message.reply_video(video=file_to_send, caption=f"🎥 **Uploaded:** `{filename}`", parse_mode="Markdown")
            elif 'audio' in mime_type:
                await update.message.reply_audio(audio=file_to_send, caption=f"🎵 **Uploaded:** `{filename}`", parse_mode="Markdown")
            else:
                await update.message.reply_document(document=file_to_send, caption=f"📄 **Uploaded:** `{filename}`", parse_mode="Markdown")

        # Upload complete hone par task cancel aur file delete
        upload_task.cancel()
        
        if os.path.exists(filename):
            os.remove(filename)
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"❌ **Error:**\n`{str(e)}`")
        if os.path.exists(filename):
            os.remove(filename)

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN nahi mila!")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    print("Pro Bot Running with Upload & Download bars...")
    application.run_polling()

if __name__ == "__main__":
    main()
