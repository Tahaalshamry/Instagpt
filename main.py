import os
import re
import logging
from threading import Thread

import requests
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("API_KEY", "")

logging.basicConfig(level=logging.INFO)

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Instagpt bot is running ✅"

def keep_alive():
    web_app.run(host="0.0.0.0", port=8080)

INSTAGRAM_URL = re.compile(r"(https?://)?(www\.)?instagram\.com/[^\s]+", re.I)
USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")

def clean_url(text):
    match = INSTAGRAM_URL.search(text)
    if not match:
        return None
    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    return url.split("?")[0].rstrip("/") + "/"

def get_username(text):
    text = text.strip().replace("@", "")
    if USERNAME.match(text):
        return text
    url = clean_url(text)
    if url:
        parts = url.rstrip("/").split("/")
        if len(parts) >= 4 and parts[-2] not in ["p", "reel", "reels", "stories"]:
            return parts[-1]
    return None

def public_profile(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.find("title")
        desc = soup.find("meta", attrs={"name": "description"})
        img = soup.find("meta", property="og:image")

        return {
            "username": username,
            "url": url,
            "title": title.get_text(" ", strip=True) if title else username,
            "description": desc.get("content", "غير متوفر") if desc else "غير متوفر",
            "image": img.get("content", "") if img else ""
        }
    except:
        return None

def external_api(action, value):
    if not API_BASE_URL:
        return None

    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    try:
        r = requests.post(
            f"{API_BASE_URL}/instagram",
            json={"action": action, "value": value},
            headers=headers,
            timeout=40
        )
        r.raise_for_status()
        return r.json()
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "هلا بيك في Instagpt 👋\n\n"
        "دز رابط إنستغرام أو يوزر.\n\n"
        "يدعم:\n"
        "👤 معلومات الحساب\n"
        "🖼 الصورة الشخصية\n"
        "📥 تجهيز تحميل الريلز/البوست/الستوري عبر API\n"
        "👀 مشاهدة الستوري عبر API\n\n"
        "ملاحظة: البوت لا يطلب يوزرنيم أو باسورد من المستخدم."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "طريقة الاستخدام:\n\n"
        "دز يوزر مثل:\n"
        "@instagram\n\n"
        "أو دز رابط:\n"
        "ريلز / بوست / ستوري"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    url = clean_url(text)
    username = get_username(text)

    if url:
        if "/reel/" in url or "/reels/" in url:
            action = "download_reel"
            name = "ريلز"
        elif "/p/" in url:
            action = "download_post"
            name = "بوست"
        elif "/stories/" in url:
            action = "download_story"
            name = "ستوري"
        else:
            action = "profile"
            name = "حساب"

        result = external_api(action, url)

        if result:
            await update.message.reply_text(
                f"✅ نتيجة {name}:\n\n<code>{result}</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"✅ استلمت رابط {name}:\n{url}\n\n"
                "التحميل الحقيقي يحتاج API خارجي تضيفه في Secrets:\n"
                "API_BASE_URL\n"
                "API_KEY"
            )
        return

    if username:
        data = public_profile(username)

        if not data:
            await update.message.reply_text("ما كدرت أجيب معلومات الحساب. جرب حساب عام أو لاحقاً.")
            return

        msg = (
            "👤 <b>معلومات الحساب</b>\n\n"
            f"اليوزر: <code>{data['username']}</code>\n"
            f"العنوان: {data['title']}\n\n"
            f"البايو/المتابعين حسب المتاح:\n{data['description']}\n\n"
            f"الرابط:\n{data['url']}"
        )

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        if data["image"]:
            await update.message.reply_photo(data["image"], caption="🖼 الصورة الشخصية")
        return

    await update.message.reply_text("دز رابط إنستغرام أو يوزر صحيح.")

def main():
    if not BOT_TOKEN:
        raise RuntimeError("ضيف BOT_TOKEN داخل Secrets في Replit")

    Thread(target=keep_alive, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Bot started ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
