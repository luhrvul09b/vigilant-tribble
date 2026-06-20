import os
import subprocess
import mimetypes
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Aria2 High-Speed Downloader Bot**\n\nMujhe koi bhi direct link bhejo, main use 16 connections ke sath fast download karke upload kar dunga!"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please ek valid HTTP/HTTPS direct link bhejein.")
        return

    status_message = await update.message.reply_text("⚡ **⚡ Aria2 se download start ho raha hai...**")

    # URL se temporary name nikalna
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        filename = "downloaded_file.mp4" # Default name agar URL me na ho

    try:
        # Aria2c command: 16 connections (-x 16 -s 16) ke sath fast download
        # --min-split-size=1M taaki choti file me bhi split kaam kare
        command = [
            "aria2c",
            "-x", "16",
            "-s", "16",
            "-k", "1M",
            "--out", filename,
            url
        ]

        # Process ko run karna
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            raise Exception(f"Aria2 Error: {process.stderr}")

        # Check agar file sach me download hui hai
        if not os.path.exists(filename):
            raise Exception("File download toh hui par server par mili nahi.")

        await status_message.edit_text("📤 **Download complete! Ab Telegram par upload ho raha hai...**")

        # File extension/mime-type check karna
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or ""

        # Telegram Upload Logic
        with open(filename, 'rb') as file_to_send:
            if 'video' in mime_type:
                await update.message.reply_video(video=file_to_send, caption=f"🎥 **Video Loaded:** `{filename}`", parse_mode="Markdown")
            elif 'audio' in mime_type:
                await update.message.reply_audio(audio=file_to_send, caption=f"🎵 **Audio Loaded:** `{filename}`", parse_mode="Markdown")
            elif 'image' in mime_type:
                await update.message.reply_photo(photo=file_to_send, caption=f"🖼️ **Image Loaded:** `{filename}`", parse_mode="Markdown")
            else:
                await update.message.reply_document(document=file_to_send, caption=f"📄 **File Loaded:** `{filename}`", parse_mode="Markdown")

        # Clean up (file delete karna)
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

    print("Aria2 Bot ready aur running hai...")
    application.run_polling()

if __name__ == "__main__":
    main()
