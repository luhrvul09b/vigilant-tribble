import os
import re
import time
import shutil
import asyncio
import mimetypes
from urllib.parse import urlparse
from pyrogram import Client, filters
from pyrogram.types import Message

# Variables from Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Pyrogram Client Initialize
app = Client("fast_downloader_bot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_readable_size(size_in_bytes):
    if not size_in_bytes:
        return "0 B"
    index = 0
    while size_in_bytes >= 1024 and index < 4:
        size_in_bytes /= 1024
        index += 1
    return f"{size_in_bytes:.2f} {['B', 'KB', 'MB', 'GB', 'TB'][index]}"

def generate_progress_bar(percentage):
    pct_num = int(percentage)
    bars = pct_num // 10
    return "■" * bars + "□" * (10 - bars)

# Pyrogram's Native Upload Progress Tracker
async def upload_progress(current, total, status_message, start_time, filename):
    now = time.time()
    
    if hasattr(status_message, 'last_update_time'):
        if (now - status_message.last_update_time) < 3 and current != total:
            return
            
    status_message.last_update_time = now
    diff = now - start_time
    speed = current / diff if diff > 0 else 0
    percentage = (current / total) * 100
    
    progress_bar = generate_progress_bar(percentage)
    dl_str = get_readable_size(current)
    tot_str = get_readable_size(total)
    spd_str = get_readable_size(speed)

    text = (
        f"📤 **Uploading to Telegram (up to 2GB)...**\n\n"
        f"📁 **File:** `{filename}`\n"
        f"📊 **Progress:** `[{progress_bar}] {percentage:.1f}%`\n"
        f"⚙️ **Status:** `{dl_str} / {tot_str}`\n"
        f"⚡ **Speed:** `{spd_str}/s`"
    )
    try:
        await status_message.edit_text(text)
    except Exception:
        pass

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("🚀 **Ultra Fast Pyrogram Downloader (2GB Limit)**\n\nMujhe link bhejein, main max speed me download karke upload kar dunga!")

@app.on_message(filters.text & ~filters.regex(r"^/"))
async def handle_link(client, message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply_text("❌ Please ek valid HTTP/HTTPS direct link bhejein.")
        return

    status_message = await message.reply_text("⚡ **Aria2 Turbo Engine Start ho raha hai...**")
    
    # Har download ke liye ek unique temporary directory banate hain
    download_dir = f"dl_{int(time.time())}"
    os.makedirs(download_dir, exist_ok=True)
    
    filename = "downloaded_file.mp4" # Fallback name display ke liye

    try:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        command = [
            "aria2c",
            "-x", "16",
            "-s", "16",
            "--continue=true",
            f"--user-agent={user_agent}",
            "--max-tries=10",
            "--retry-wait=3",
            "--summary-interval=1",
            "--content-disposition-default-utf8=true",
            "--dir", download_dir,  # File is specific folder me hi download hogi
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
            
            # Agar log sa filename mil jaye to text progress me show karne ke liye update kar dein
            if "Destination:" in line:
                extracted_name = line.split("Destination:")[-1].strip()
                if extracted_name:
                    filename = os.path.basename(extracted_name)

            match = re.search(r'\[#\w+\s+([\d\w\.]+)/([\d\w\.]+)\(([\d%]+)\)\s+CN:\d+\s+DL:([\d\w\.]+)(?:.*)\]', line)
            
            if match:
                downloaded = match.group(1)   
                total_size = match.group(2)   
                percentage_str = match.group(3)   
                speed = match.group(4)        

                if time.time() - last_edit_time >= 3:
                    try:
                        pct_num = float(percentage_str.replace('%', ''))
                        progress_bar = generate_progress_bar(pct_num)
                    except:
                        progress_bar = "■■■■■■■■■■"

                    text = (
                        f"📥 **Downloading (16x Turbo)...**\n\n"
                        f"📁 **File:** `{filename}`\n"
                        f"📊 **Progress:** `[{progress_bar}] {percentage_str}`\n"
                        f"⚙️ **Status:** `{downloaded} / {total_size}`\n"
                        f"⚡ **Speed:** `{speed}/s`"
                    )
                    try:
                        await status_message.edit_text(text)
                        last_edit_time = time.time()
                    except Exception:
                        pass

        await process.wait()

        if process.returncode != 0:
            raise Exception("Aria2 download fail. Link expire ho gayi ya server issue hai.")

        # --- NEW LOGIC TO FIND THE FILE ---
        # download_dir check karo aur jo bhi file andar mili, usko final path bana lo
        files_in_dir = os.listdir(download_dir)
        if not files_in_dir:
            raise Exception("Downloaded file nahi mili directory me.")
        
        # Pehli valid file uthao (aria2 temp files ko ignore karne ke liye filtering)
        downloaded_file_name = [f for f in files_in_dir if not f.endswith(('.aria2', '.json'))][0]
        file_path = os.path.join(download_dir, downloaded_file_name)
        filename = downloaded_file_name # Real filename override for telegram caption

        await status_message.edit_text("📤 **Download mukammal! Pyrogram ke zariye upload shuru...**")
        
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or ""

        start_time = time.time()
        status_message.last_update_time = time.time()
        
        # Pyrogram Built-in Uploader using strict file_path
        if 'video' in mime_type or filename.lower().endswith(('.mkv', '.mp4', '.avi', '.mov')):
            await message.reply_video(
                video=file_path,
                caption=f"🎥 **Uploaded:** `{filename}`",
                progress=upload_progress,
                progress_args=(status_message, start_time, filename)
            )
        elif 'audio' in mime_type:
            await message.reply_audio(
                audio=file_path,
                caption=f"🎵 **Uploaded:** `{filename}`",
                progress=upload_progress,
                progress_args=(status_message, start_time, filename)
            )
        else:
            await message.reply_document(
                document=file_path,
                caption=f"📄 **Uploaded:** `{filename}`",
                progress=upload_progress,
                progress_args=(status_message, start_time, filename)
            )

        # Cleanup target dir completely
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"❌ **Error:**\n`{str(e)}`")
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)

if __name__ == "__main__":
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        print("Error: API_ID, API_HASH, ya BOT_TOKEN missing hai Railway variables me!")
    else:
        print("Pyrogram Ultra Fast Bot Running...")
        app.run()
