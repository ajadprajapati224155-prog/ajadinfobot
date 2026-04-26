import logging
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────────────────────────
#  CONFIG — Render pe environment variables set karo
# ─────────────────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Force join ke liye apna channel username dalo (@ ke bina)
# Render pe CHANNEL_USERNAME environment variable set karo
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "mychannel")

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
#  FORCE JOIN CHECK
# ─────────────────────────────────────────────
async def is_member(bot, user_id: int) -> bool:
    """Check karo user channel ka member hai ya nahi."""
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def send_join_prompt(update: Update):
    """Join karne ka button bhejo."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ Maine Join Kar Liya", callback_data="check_join")],
    ])
    await update.message.reply_text(
        "🔒 *Bot use karne ke liye pehle channel join karo!*\n\n"
        f"👉 Channel: @{CHANNEL_USERNAME}\n\n"
        "Join karne ke baad *'Maine Join Kar Liya'* button dabao.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────
#  TRUECALLER HELPER
# ─────────────────────────────────────────────
def fetch_truecaller_info(number: str) -> dict:
    try:
        res = requests.get(
            TRUECALLER_API_URL,
            params={"key": TRUECALLER_API_KEY, "q": number},
            timeout=10,
        )
        data = res.json()

        # API list ya dict dono return kar sakta hai
        result = data.get("result", {})
        results_list = []

        if isinstance(result, list):
            results_list = result
        elif isinstance(result, dict) and result:
            results_list = [result]

        if not results_list:
            return {"success": False, "error": "❌ Koi information nahi mili is number ke liye."}

        return {"success": True, "results": results_list, "raw_number": number}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "⏳ API timeout ho gaya. Dobara try karo."}
    except Exception as e:
        logger.error(f"Truecaller API error: {e}")
        return {"success": False, "error": f"❌ Error: {e}"}


def clean_number(number: str) -> str:
    """WhatsApp/Telegram link ke liye number clean karo."""
    n = number.strip()
    digits = n.replace("+", "").replace(" ", "").replace("-", "")
    if not n.startswith("+"):
        # 10 digit Indian number
        if len(digits) == 10:
            n = "+91" + digits
        else:
            n = "+" + digits
    return n


def format_info_message(data: dict) -> str:
    """Screenshot jaise format mein message banao."""
    number    = data["raw_number"]
    clean_num = clean_number(number)
    results   = data["results"]

    country = results[0].get("country", "India")
    flag    = "🇮🇳" if "india" in country.lower() else "🌍"

    lines = [
        f"📞 *Number:* `{clean_num}`",
        f"🌍 *Country:* {country} {flag}",
        "",
    ]

    source_labels = ["🔍 *TrueCaller Says:*", "🔍 *Unknown Says:*"]

    for i, result in enumerate(results):
        label   = source_labels[i] if i < len(source_labels) else f"🔍 *Result {i+1}:*"
        name    = result.get("name")     or "N/A"
        carrier = result.get("carrier")  or result.get("operator") or None
        city    = result.get("city")     or result.get("location") or None

        lines.append(label)
        lines.append(f"👤 *Name:* {name}")
        if carrier:
            lines.append(f"📡 *Carrier:* {carrier}")
        if city:
            lines.append(f"📍 *Location:* {city}")
        lines.append("")

    return "\n".join(lines).strip()


def build_contact_keyboard(number: str) -> InlineKeyboardMarkup:
    """WhatsApp aur Telegram direct open buttons."""
    clean_num = clean_number(number)
    wa_num = clean_num.replace("+", "")
    wa_url = f"https://wa.me/{wa_num}"
    tg_url = f"https://t.me/+{wa_num}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 WhatsApp", url=wa_url),
            InlineKeyboardButton("✈️ Telegram", url=tg_url),
        ]
    ])


# ─────────────────────────────────────────────
#  TELEGRAM HANDLERS
# ─────────────────────────────────────────────
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_member(context.bot, user_id):
        await send_join_prompt(update)
        return

    await update.message.reply_text(
        "👋 *Truecaller Info Bot* mein aapka swagat hai!\n\n"
        "📞 Kisi bhi phone number ki info pane ke liye:\n\n"
        "➡️  `/num <number>`\n\n"
        "*Example:*\n"
        "`/num +919876543210`\n"
        "`/num 9876543210`\n\n"
        "💡 Number mein country code lagana behtar hota hai.",
        parse_mode="Markdown",
    )


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Maine Join Kar Liya' button press hone pe check karo."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if await is_member(context.bot, user_id):
        await query.edit_message_text(
            "✅ *Shukriya join karne ke liye!*\n\n"
            "Ab aap bot use kar sakte hain 🎉\n\n"
            "📞 Number search karne ke liye:\n"
            "`/num 9876543210`",
            parse_mode="Markdown",
        )
    else:
        await query.answer(
            "❌ Aapne abhi join nahi kiya! Pehle channel join karo.",
            show_alert=True,
        )


async def num_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/num command — number ki info fetch karo."""
    user_id = update.effective_user.id

    if not await is_member(context.bot, user_id):
        await send_join_prompt(update)
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Number do please!\n\n"
            "Usage: `/num +919876543210`",
            parse_mode="Markdown",
        )
        return

    number = context.args[0].strip()
    digits_only = number.replace("+", "").replace(" ", "").replace("-", "")

    if not digits_only.isdigit() or len(digits_only) < 7:
        await update.message.reply_text(
            "❌ Invalid number format!\n"
            "Example: `/num +919876543210`",
            parse_mode="Markdown",
        )
        return

    loading_msg = await update.message.reply_text("🔍 Searching...")

    info = fetch_truecaller_info(number)

    if not info["success"]:
        await loading_msg.edit_text(
            f"❌ *Error:* {info['error']}",
            parse_mode="Markdown",
        )
        return

    text     = format_info_message(info)
    keyboard = build_contact_keyboard(number)
    image    = info["results"][0].get("image") if info.get("results") else None

    if image:
        try:
            await loading_msg.delete()
            await update.message.reply_photo(
                photo=image,
                caption=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await loading_msg.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def plain_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sirf number type karne pe bhi kaam kare."""
    user_id = update.effective_user.id

    if not await is_member(context.bot, user_id):
        await send_join_prompt(update)
        return

    text   = update.message.text.strip()
    digits = text.replace("+", "").replace(" ", "").replace("-", "")

    if digits.isdigit() and len(digits) >= 7:
        context.args = [text]
        await num_handler(update, context)
    else:
        await update.message.reply_text(
            "🤔 Kuch samajh nahi aaya!\n"
            "Phone number search ke liye `/num <number>` use karo.",
            parse_mode="Markdown",
        )


# ─────────────────────────────────────────────
#  KEEP-ALIVE SERVER (Render + UptimeRobot)
# ─────────────────────────────────────────────
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    logger.info(f"Keep-alive server running on port {port}")
    server.serve_forever()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=run_keep_alive, daemon=True)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("num", num_handler))
    app.add_handler(CommandHandler("lookup", num_handler))  # purana command bhi kaam kare
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plain_number_handler))

    logger.info("✅ Truecaller Bot chal raha hai...")
    app.run_polling(drop_pending_updates=True)
