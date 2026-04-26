import logging
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────────────────────────
#  CONFIG — Render pe environment variables set karo
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

TRUECALLER_API_URL = "https://ansh-apis.is-dev.org/api/truecaller"
TRUECALLER_API_KEY = "ansh"

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  TRUECALLER HELPER
# ─────────────────────────────────────────────
def fetch_truecaller_info(number: str) -> dict:
    """
    Truecaller API se number ki info fetch karo.
    Returns a dict with keys: name, number, carrier, city, country, image
    """
    try:
        res = requests.get(
            TRUECALLER_API_URL,
            params={"key": TRUECALLER_API_KEY, "q": number},
            timeout=10,
        )
        data = res.json()
        result = data.get("result", {})

        return {
            "success": True,
            "name":    result.get("name")    or "N/A",
            "number":  result.get("number")  or number,
            "carrier": result.get("carrier") or "N/A",
            "city":    result.get("city")    or "N/A",
            "country": result.get("country") or "N/A",
            "image":   result.get("image"),
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "⏳ API timeout ho gaya. Dobara try karo."}
    except Exception as e:
        logger.error(f"Truecaller API error: {e}")
        return {"success": False, "error": f"❌ Error: {e}"}


def format_info_message(info: dict) -> str:
    """Bot reply message banao."""
    return (
        f"📋 *Phone Number Info*\n"
        f"{'─' * 28}\n"
        f"👤 *Name:*    {info['name']}\n"
        f"📞 *Number:*  `{info['number']}`\n"
        f"📡 *Carrier:* {info['carrier']}\n"
        f"🏙️ *City:*    {info['city']}\n"
        f"🌍 *Country:* {info['country']}\n"
        f"{'─' * 28}\n"
        f"_Powered by Truecaller API_"
    )


# ─────────────────────────────────────────────
#  TELEGRAM HANDLERS
# ─────────────────────────────────────────────
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Truecaller Info Bot* mein aapka swagat hai!\n\n"
        "📞 Kisi bhi phone number ki info pane ke liye:\n\n"
        "➡️  `/lookup <number>`\n\n"
        "*Example:*\n"
        "`/lookup +919876543210`\n"
        "`/lookup 9876543210`\n\n"
        "💡 Number mein country code lagana behtar hota hai.",
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Help*\n\n"
        "• `/start` — Bot shuru karo\n"
        "• `/lookup <number>` — Number ki info dekho\n"
        "• `/help` — Yeh message\n\n"
        "*Tips:*\n"
        "✅ `+91` country code lagao for India\n"
        "✅ Spaces mat do number mein",
        parse_mode="Markdown",
    )


async def lookup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /lookup +919876543210
    Ya sirf number bhi type kar sakte hain.
    """
    if not context.args:
        await update.message.reply_text(
            "⚠️ Number do please!\n\n"
            "Usage: `/lookup +919876543210`",
            parse_mode="Markdown",
        )
        return

    number = context.args[0].strip()

    # Basic validation
    digits_only = number.replace("+", "").replace(" ", "")
    if not digits_only.isdigit() or len(digits_only) < 7:
        await update.message.reply_text(
            "❌ Invalid number format!\n"
            "Example: `/lookup +919876543210`",
            parse_mode="Markdown",
        )
        return

    # Loading message
    loading_msg = await update.message.reply_text("🔍 Searching...")

    info = fetch_truecaller_info(number)

    if not info["success"]:
        await loading_msg.edit_text(
            f"❌ *Error:* {info['error']}",
            parse_mode="Markdown",
        )
        return

    text = format_info_message(info)

    # Agar profile image available hai toh photo bhejo
    if info.get("image"):
        try:
            await loading_msg.delete()
            await update.message.reply_photo(
                photo=info["image"],
                caption=text,
                parse_mode="Markdown",
            )
            return
        except Exception:
            pass  # Image fail ho toh text se kaam chalao

    await loading_msg.edit_text(text, parse_mode="Markdown")


async def plain_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Agar user sirf number type kare (bina /lookup ke) toh bhi kaam kare.
    """
    text = update.message.text.strip()
    digits = text.replace("+", "").replace(" ", "").replace("-", "")

    if digits.isdigit() and len(digits) >= 7:
        # Fake karo jaise /lookup call hua
        context.args = [text]
        await lookup_handler(update, context)
    else:
        await update.message.reply_text(
            "🤔 Kuch samajh nahi aaya!\n"
            "Phone number lookup ke liye `/lookup <number>` use karo.",
            parse_mode="Markdown",
        )


# ─────────────────────────────────────────────
#  KEEP-ALIVE SERVER (Render free tier ke liye)
# ─────────────────────────────────────────────
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        # UptimeRobot HEAD request ke liye
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # Server logs suppress karo


def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    logger.info(f"Keep-alive server running on port {port}")
    server.serve_forever()


# ─────────────────────────────────────────────
#  MAIN  (sync — Python 3.14 fix)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Keep-alive thread (Render free tier ke liye)
    t = threading.Thread(target=run_keep_alive, daemon=True)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("lookup", lookup_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, plain_number_handler)
    )

    logger.info("✅ Truecaller Bot chal raha hai...")
    # run_polling() sync hai — asyncio.run() mat lagao
    app.run_polling(drop_pending_updates=True)
