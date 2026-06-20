import os
import re
import time
import subprocess
import mimetypes
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Aria2 High-Speed Downloader Bot**\n\nMujhe koi bhi direct link bhejo, main use live download progress aur speed meter ke sath upload kar dunga!"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please ek valid HTTP/HTTPS direct link bhejein.")
        return

    status_message = await update.message.reply_text("⚡ **Aria2 engine start ho raha hai...**")

    # URL se file name nikalna
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        filename = "downloaded_file.mp4"

    try:
        # Aria2 command (16 connections)
        command = [
            "aria2c",
            "-x", "16",
            "-s", "16",
            "-k", "1M",
            "--out", filename,
            url
        ]

        # Background process open kiya stdout redirection ke sath
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1
        )
        
        last_edit_time = time.time()

        # Aria2 ke terminal output ko line-by-line read karenge
        for line in iter(process.stdout.readline, ''):
            # Regex pattern aria2 ke standard progress line ko match karne ke liye
            # Example log line: [#242345 1.2MiB/4.5MiB(26%) CN:16 DL:2.4MiB]
            match = re.search(r'\[#\w+\s+([\d\w\.]+)/([\d\w\.]+)\(([\d%]+)\)\s+CN:\d+\s+DL:([\d\w\.]+)(?:.*)\]', line)
            
            if match:
                downloaded = match.group(1)   # Kitna size ho gaya (e.g., 12MB)
                total_size = match.group(2)   # Total size kitna hai (e.g., 50MB)
                percentage = match.group(3)   # Percentage (e.g., 24%)
                speed = match.group(4)        # Current download speed (e.g., 4.5MiB)

                # Telegram ko rate limit se bachane ke liye har 4 second me sirf 1 baar edit karenge
                if time.time() - last_edit_time > 4:
                    # Ek badhiya sa progress bar generate karte hain
                    pct_num = int(percentage.replace('%', ''))
                    bars = int(pct_num / 10)
                    progress_bar = "■" * bars + "□" * (10 - bars)

                    progress_text = (
                        f"📥 **Downloading File...**\n\n"
                        f"📁 **File:** `{filename}`\n"
                        f"📊 **Progress:** `[{progress_bar}] {percentage}`\n"
                        f"⚙️ **Status:** `{downloaded} / {total_size}`\n"
                        f"⚡ **Speed:** `{speed}/s`"
                    )
                    try:
                        await status_message.edit_text(progress_text, parse_mode="Markdown")
                        last_edit_time = time.time()
                    except Exception:
                        pass # Agar telegram same message block kare to ignore karo

        process.wait()

        if process.returncode != 0:
            raise Exception("Aria2 download fail ho gaya ya link expire ho gayi.")

        await status_message.edit_text("📤 **Download complete! Telegram par upload ho raha hai...**")

        # Mime-type check aur upload handling
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or ""

        with open(filename, 'rb') as file_to_send:
            if 'video' in mime_type:
                await update.message.reply_video(video=file_to_send, caption=f"🎥 **Video Loaded:** `{filename}`", parse_mode="Markdown")
            elif 'audio' in mime_type:
                await update.message.reply_audio(audio=file_to_send, caption=f"🎵 **Audio Loaded:** `{filename}`", parse_mode="Markdown")
            elif 'image' in mime_type:
                await update.message.reply_photo(photo=file_to_send, caption=f"🖼️ **Image Loaded:** `{filename}`", parse_mode="Markdown")
            else:
                await update.message.reply_document(document=file_to_send, caption=f"📄 **File Loaded:** `{filename}`", parse_mode="Markdown")

        # Server space free karna
        if os.path.exists(filename):
            os.remove(filename)
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"❌ **Error Aagaya:**\n`{str(e)}`")
        if os.path.exists(filename):
            os.remove(filename)

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN nahi mila!")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    print("Aria2 Live Tracker Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()
