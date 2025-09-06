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

# ---------------- CONFIG (read from env) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")                 # set on host
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")         # set on host (must be negative)
if GROUP_CHAT_ID:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)

# Validate env
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment variable is required.")
if not GROUP_CHAT_ID:
    raise SystemExit("GROUP_CHAT_ID environment variable is required (negative number).")

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- Conversation states ----------------
COUNT, SOURCE, DEST, DATE, TRAIN, GENDER, PRICE, CONFIRM = range(8)

# ---------------- Helpers ----------------
def parse_date_yyyy_mm_dd(s: str):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def gender_normalize(s: str):
    s = s.strip().lower()
    if s in ("m", "male"):
        return "Male"
    if s in ("f", "female"):
        return "Female"
    if s in ("other", "o"):
        return "Other"
    return None

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["Sell Ticket"]]
    reply = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome to Indian Train Tickets Bot.\n\nPress the button to sell a ticket.",
        reply_markup=reply,
    )

async def sell_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Entry to conversation, triggered by the keyboard or /sell
    context.user_data.clear()
    await update.message.reply_text("How many tickets do you want to sell? (number)", reply_markup=ReplyKeyboardRemove())
    return COUNT

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt.isdigit() or int(txt) <= 0:
        await update.message.reply_text("Please send a valid positive integer for ticket count.")
        return COUNT
    count = int(txt)
    context.user_data["count"] = count
    context.user_data["genders"] = []
    context.user_data["gender_index"] = 0
    await update.message.reply_text("Enter Source station (e.g., Chennai):")
    return SOURCE

async def ask_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source"] = update.message.text.strip()
    await update.message.reply_text("Enter Destination station (e.g., Trivandrum):")
    return DEST

async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dest"] = update.message.text.strip()
    await update.message.reply_text("Enter Journey date (YYYY-MM-DD):")
    return DATE

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    d = parse_date_yyyy_mm_dd(txt)
    if not d:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-29). Try again:")
        return DATE
    if d < date.today():
        await update.message.reply_text("Date cannot be in the past. Enter a future date (YYYY-MM-DD):")
        return DATE
    context.user_data["date"] = d.isoformat()
    await update.message.reply_text("Enter Train Number (e.g., 16605):")
    return TRAIN

async def ask_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["train"] = update.message.text.strip()
    # start gender questions
    context.user_data["gender_index"] = 1
    await update.message.reply_text(f"Enter gender of passenger 1 (Male/Female/Other):")
    return GENDER

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = gender_normalize(update.message.text)
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
        await update.message.reply_text("Invalid price. Enter a numeric value (e.g., 1200):")
        return PRICE
    context.user_data["price"] = price

    # show summary with Confirm/Cancel instruction
    info = context.user_data
    summary = (
        f"Please confirm your ticket:\n\n"
        f"From: {info['source']} → {info['dest']}\n"
        f"Date: {info['date']}\n"
        f"Train: {info['train']}\n"
        f"Tickets: {info['count']}\n"
        f"Genders: {', '.join(info['genders'])}\n"
        f"Price: ₹{info['price']}\n\n"
        "Reply with YES to confirm and post to group, or NO to cancel."
    )
    await update.message.reply_text(summary)
    return CONFIRM

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt not in ("yes", "y"):
        await update.message.reply_text("Submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    info = context.user_data
    # Build message for group
    post = (
        f"🎫 New Ticket Available 🎫\n\n"
        f"🚉 {info['source']} → {info['dest']}\n"
        f"📅 {info['date']} | 🚆 {info['train']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n\n"
        f"👉 Contact the admin to buy."
    )
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post)
    except Exception as e:
        logger.exception("Failed to post to group: %s", e)
        await update.message.reply_text("Failed to post to group — please check group ID and that the bot is admin.")
        return ConversationHandler.END

    await update.message.reply_text("✅ Your ticket has been posted to the group. Thank you!")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------------- Main ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("sell", sell_entry),
            MessageHandler(filters.Regex("^(Sell Ticket)$") & ~filters.COMMAND, sell_entry),
        ],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_count)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_source)],
            DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_train)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_post)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="sell_conv",
        persistent=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    logger.info("Bot polling starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
