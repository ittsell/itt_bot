# bot.py -- polling bot, always-on friendly, no DB (simple JSON optional)
import os
import logging
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read config from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")   # must be a string like -1001234567890
ADMIN_ID = os.getenv("ADMIN_ID")             # optional: for notifications

if not BOT_TOKEN or not GROUP_CHAT_ID:
    logger.error("BOT_TOKEN and GROUP_CHAT_ID environment variables must be set.")
    raise SystemExit("Set BOT_TOKEN and GROUP_CHAT_ID env vars")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except:
    raise SystemExit("GROUP_CHAT_ID must be an integer (negative for groups)")

# Conversation states
COUNT, SOURCE, DEST, DATE, TRAIN, GENDER, PRICE, CONFIRM = range(8)

# Keep per-user conversation data in context.user_data (built-in); no DB required.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("🎟 Sell Ticket")]]
    await update.message.reply_text("Welcome to Indian Train Tickets (ITT).\nClick Sell Ticket to begin.",
                                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))

# entrypoint for sell: user clicks button or types /sell
async def sell_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Please message me in private (DM) to sell tickets.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("How many tickets do you want to sell? (enter a number)")
    return COUNT

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt.isdigit() or int(txt) <= 0:
        await update.message.reply_text("Enter a valid positive integer for ticket count.")
        return COUNT
    context.user_data["count"] = int(txt)
    context.user_data["genders"] = []
    await update.message.reply_text("Enter Source station (e.g., Chennai):")
    return SOURCE

async def ask_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source"] = update.message.text.strip()
    await update.message.reply_text("Enter Destination station (e.g., Trivandrum):")
    return DEST

def parse_date_iso(s: str):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except:
        return None

async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["destination"] = update.message.text.strip()
    await update.message.reply_text("Enter Journey Date (YYYY-MM-DD):")
    return DATE

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    d = parse_date_iso(txt)
    if not d:
        await update.message.reply_text("Invalid date. Use YYYY-MM-DD (e.g., 2025-10-29). Try again:")
        return DATE
    if d < date.today():
        await update.message.reply_text("Date is before today. Please enter a future date (YYYY-MM-DD):")
        return DATE
    context.user_data["date"] = d.isoformat()
    await update.message.reply_text("Enter Train number (e.g., 16605):")
    return TRAIN

async def ask_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["train"] = update.message.text.strip()
    # start gender questions
    context.user_data["genders"] = []
    context.user_data["gender_index"] = 1
    await update.message.reply_text(f"Enter gender for passenger 1 (Male/Female/Other):")
    return GENDER

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().title()
    if txt not in ("Male", "Female", "Other"):
        await update.message.reply_text("Please reply Male, Female, or Other.")
        return GENDER
    context.user_data["genders"].append(txt)
    if len(context.user_data["genders"]) < context.user_data["count"]:
        context.user_data["gender_index"] += 1
        await update.message.reply_text(f"Enter gender for passenger {context.user_data['gender_index']}:")
        return GENDER
    # done collecting genders
    await update.message.reply_text("Enter total ticket price in ₹ (numbers only):")
    return PRICE

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        price = float(txt)
        if price <= 0:
            raise ValueError()
    except:
        await update.message.reply_text("Enter a valid numeric price (e.g., 250).")
        return PRICE
    context.user_data["price"] = price

    # summary & confirm
    summary = (
        f"Please confirm your ticket details:\n\n"
        f"From: {context.user_data['source']} → {context.user_data['destination']}\n"
        f"Date: {context.user_data['date']}\n"
        f"Train: {context.user_data['train']}\n"
        f"Tickets: {context.user_data['count']}\n"
        f"Genders: {', '.join(context.user_data['genders'])}\n"
        f"Price: ₹{context.user_data['price']}\n\n"
        "Reply YES to post to group, or NO to cancel."
    )
    await update.message.reply_text(summary)
    return CONFIRM

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt not in ("yes", "y"):
        await update.message.reply_text("Submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    # Compose message to group and post directly
    seller = update.effective_user
    ticket_text = (
        f"🎫 New Ticket Posted\n\n"
        f"From: {context.user_data['source']} → {context.user_data['destination']}\n"
        f"Date: {context.user_data['date']}\n"
        f"Train: {context.user_data['train']}\n"
        f"Tickets: {context.user_data['count']}\n"
        f"Genders: {', '.join(context.user_data['genders'])}\n"
        f"💰 Price: ₹{context.user_data['price']}\n\n"
        f"Contact admin to buy."
    )

    # post to group
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=ticket_text)
    except Exception as e:
        logger.exception("Failed to post to group: %s", e)
        await update.message.reply_text("Failed to post to group. Make sure bot is admin in the group and GROUP_CHAT_ID is correct.")
        return ConversationHandler.END

    # optionally notify admin privately including seller id
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=int(ADMIN_ID),
                                           text=f"Ticket posted by @{seller.username or seller.id} (id {seller.id}). Price: ₹{context.user_data['price']}")
        except Exception:
            pass

    await update.message.reply_text("✅ Ticket posted to group. Thank you!")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("sell", sell_entry),
                      MessageHandler(filters.Regex("^🎟 Sell Ticket$"), sell_entry)],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_count)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_source)],
            DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_train)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_submission)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    logger.info("Bot starting (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
