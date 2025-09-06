# bot.py
import os
import logging
from datetime import datetime, date
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

# ---------- CONFIG (env vars) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")                  # required
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")          # required (string; convert to int)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")              # e.g. https://your-service.onrender.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")            # optional; default uses token prefix
PORT = int(os.getenv("PORT", "8443"))               # Render will provide PORT automatically

if not BOT_TOKEN:
    raise SystemExit("Missing BOT_TOKEN environment variable")
if not GROUP_CHAT_ID:
    raise SystemExit("Missing GROUP_CHAT_ID environment variable")

GROUP_CHAT_ID = int(GROUP_CHAT_ID)

if not WEBHOOK_PATH:
    WEBHOOK_PATH = BOT_TOKEN.split(":")[0]

# ---------- logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- conversation states ----------
COUNT, SOURCE, DEST, DATE_S, TRAIN, GENDER, PRICE, CONFIRM = range(8)

# ---------- helpers ----------
def parse_date_yyyy_mm_dd(s: str):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def normalize_gender(s: str):
    s = s.strip().lower()
    if s in ("m", "male"): return "Male"
    if s in ("f", "female"): return "Female"
    if s in ("o", "other"): return "Other"
    return None

# ---------- handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["Sell Ticket"]]
    await update.message.reply_text(
        "Welcome to Indian Train Tickets Bot.\nPress the button to sell a ticket.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True),
    )

async def sell_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # start the conversation
    context.user_data.clear()
    await update.message.reply_text("How many tickets do you want to sell?", reply_markup=ReplyKeyboardRemove())
    return COUNT

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("Please enter a valid positive integer for ticket count.")
        return COUNT
    context.user_data["count"] = int(text)
    context.user_data["genders"] = []
    await update.message.reply_text("Enter Source station (e.g., Chennai):")
    return SOURCE

async def ask_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source"] = update.message.text.strip()
    await update.message.reply_text("Enter Destination station (e.g., Trivandrum):")
    return DEST

async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dest"] = update.message.text.strip()
    await update.message.reply_text("Enter Journey date (YYYY-MM-DD):")
    return DATE_S

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    d = parse_date_yyyy_mm_dd(txt)
    if not d:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-29). Try again:")
        return DATE_S
    if d < date.today():
        await update.message.reply_text("Date cannot be in the past. Enter a future date (YYYY-MM-DD):")
        return DATE_S
    context.user_data["date"] = d.isoformat()
    await update.message.reply_text("Enter Train number (e.g., 16605):")
    return TRAIN

async def ask_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["train"] = update.message.text.strip()
    # begin gender loop
    await update.message.reply_text("Enter gender of passenger 1 (Male/Female/Other):")
    return GENDER

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = normalize_gender(update.message.text)
    if not g:
        await update.message.reply_text("Invalid gender. Reply with Male, Female or Other:")
        return GENDER
    context.user_data["genders"].append(g)
    if len(context.user_data["genders"]) < context.user_data["count"]:
        idx = len(context.user_data["genders"]) + 1
        await update.message.reply_text(f"Enter gender of passenger {idx} (Male/Female/Other):")
        return GENDER
    # all genders collected
    await update.message.reply_text("Enter total ticket price (in ₹):")
    return PRICE

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        price = float(txt)
        if price < 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("Invalid price. Enter a numeric value (e.g., 1200).")
        return PRICE
    context.user_data["price"] = price

    info = context.user_data
    summary = (
        f"Please confirm your ticket:\n\n"
        f"From: {info['source']} → {info['dest']}\n"
        f"Date: {info['date']} | Train: {info['train']}\n"
        f"Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"Price: ₹{info['price']}\n\n"
        "Reply YES to post to the group, or NO to cancel."
    )
    await update.message.reply_text(summary)
    return CONFIRM

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt not in ("yes","y"):
        await update.message.reply_text("Submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    info = context.user_data
    post = (
        f"🎫 New Ticket Available 🎫\n\n"
        f"🚉 {info['source']} → {info['dest']}\n"
        f"📅 {info['date']} | 🚆 {info['train']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n\n"
        "👉 Contact the admin to buy."
    )

    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post)
    except Exception as e:
        logger.exception("Failed to post to group: %s", e)
        await update.message.reply_text("Failed to post to group. Ensure the bot is added to the group and has message permissions.")
        return ConversationHandler.END

    await update.message.reply_text("✅ Your ticket has been posted to the group.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- main ----------
def main():
    # increase timeouts for cloud environments
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("sell", sell_entry), MessageHandler(filters.Regex("^(Sell Ticket)$") & ~filters.COMMAND, sell_entry), CommandHandler("start", start)],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_count)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_source)],
            DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            DATE_S: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_train)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_post)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="sell_conv",
        persistent=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))

    logger.info("Starting bot. WEBHOOK_URL=%s, PATH=%s, PORT=%s", WEBHOOK_URL, WEBHOOK_PATH, PORT)

    # If WEBHOOK_URL is provided, use webhook mode (suitable for Render Web Service)
    if WEBHOOK_URL:
        webhook_url = WEBHOOK_URL.rstrip("/") + "/" + WEBHOOK_PATH
        logger.info("Running webhook: %s", webhook_url)
        # listen on all interfaces; Render provides PORT env var
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=WEBHOOK_PATH, webhook_url=webhook_url)
    else:
        # fallback for local testing
        logger.info("No WEBHOOK_URL provided; running long-polling (local dev).")
        app.run_polling()

if __name__ == "__main__":
    main()
