import os
import re
import time
import asyncio
import mimetypes
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Fast Aria2 Downloader Bot**\n\nMujhe link bhejein, ab aapko real-time fast progress updates milenge!"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please ek valid HTTP/HTTPS direct link bhejein.")
        return

    status_message = await update.message.reply_text("⚡ **Connecting to server...**")

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        filename = "downloaded_file.mp4"

    try:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        # Aria2 command with strict timeout and performance flags
        command = [
            "aria2c",
            "-x", "8",        # Huggingface ke liye 8 connections perfect balance hai speed aur safety ka
            "-s", "8",
            "-k", "1M",
            f"--user-agent={user_agent}",
            "--max-tries=5",
            "--connect-timeout=10",
            "--timeout=10",
            "--summary-interval=1", # Har 1 second me aria2 ko log generate karne par majboor karega
            "--out", filename,
            url
        ]

        # Asynchronous process start kiya taaki script free rahe
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        last_edit_time = time.time()

        # Pura process live line-by-line read hoga bina block hue
        while True:
            line_bytes = await process.stdout.readline()
            if not line_bytes:
                break
                
            line = line_bytes.decode('utf-8', errors='ignore')
            
            # Aria2 progress status log match karna
            match = re.search(r'\[#\w+\s+([\d\w\.]+)/([\d\w\.]+)\(([\d%]+)\)\s+CN:\d+\s+DL:([\d\w\.]+)(?:.*)\]', line)
            
            if match:
                downloaded = match.group(1)   
                total_size = match.group(2)   
                percentage = match.group(3)   
                speed = match.group(4)        

                # Pura 3 second ka hard check (Telegram policy ke mutabiq safest aur fastest speed)
                if time.time() - last_edit_time >= 3:
                    try:
                        pct_num = int(percentage.replace('%', ''))
                        bars = int(pct_num / 10)
                        progress_bar = "■" * bars + "□" * (10 - bars)
                    except:
                        progress_bar = "■■■■■■■■■■"

                    progress_text = (
                        f"📥 **Downloading (Real-time Live)...**\n\n"
                        f"📁 **File:** `{filename}`\n"
                        f"📊 **Progress:** `[{progress_bar}] {percentage}`\n"
                        f"⚙️ **Status:** `{downloaded} / {total_size}`\n"
                        f"⚡ **Speed:** `{speed}/s`"
                    )
                    try:
                        await status_message.edit_text(progress_text, parse_mode="Markdown")
                        last_edit_time = time.time()
                    except Exception:
                        pass # Agar jaldi edit hone par telegram temporary mana kare toh script crash na ho

        await process.wait()

        if process.returncode != 0:
            raise Exception("Download interrupted. Server ne session close kar diya.")

        await status_message.edit_text("📤 **Download complete! Telegram par upload ho raha hai...**")

        # File type check aur upload logic
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or ""

        with open(filename, 'rb') as file_to_send:
            if 'video' in mime_type:
                await update.message.reply_video(video=file_to_send, caption=f"🎥 **Uploaded:** `{filename}`", parse_mode="Markdown")
            elif 'audio' in mime_type:
                await update.message.reply_audio(audio=file_to_send, caption=f"🎵 **Uploaded:** `{filename}`", parse_mode="Markdown")
            else:
                await update.message.reply_document(document=file_to_send, caption=f"📄 **Uploaded:** `{filename}`", parse_mode="Markdown")

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

    print("Async Aria2 Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()
