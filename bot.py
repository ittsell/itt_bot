import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from telegram.request import HTTPXRequest

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Add this in Railway Environment
GROUP_ID = os.getenv("GROUP_ID")    # Example: -1002927412557

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- CONVERSATION STATES --------------------
FROM, TO, DATE, TRAIN, COUNT, GENDER, PRICE, CONFIRM = range(8)

# -------------------- START --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Sell Ticket"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("👋 Welcome! Use the button below to sell a ticket:", reply_markup=reply_markup)
    return FROM

async def from_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() != "sell ticket":
        await update.message.reply_text("Click the 'Sell Ticket' button to start.")
        return ConversationHandler.END
    await update.message.reply_text("🚉 Enter departure station:")
    return TO

async def to_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["from"] = update.message.text
    await update.message.reply_text("🚉 Enter destination station:")
    return DATE

async def travel_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["to"] = update.message.text
    await update.message.reply_text("📅 Enter travel date (YYYY-MM-DD):")
    return TRAIN

async def train_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    # Basic validation
    if len(date) != 10 or date[4] != "-" or date[7] != "-":
        await update.message.reply_text("❌ Invalid date format. Please enter again (YYYY-MM-DD):")
        return DATE
    context.user_data["date"] = date
    await update.message.reply_text("🚂 Enter train number:")
    return COUNT

async def ticket_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["train"] = update.message.text
    await update.message.reply_text("🎟 How many tickets?")
    return GENDER

async def ticket_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        context.user_data["count"] = count
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for ticket count:")
        return GENDER

    context.user_data["genders"] = []
    await update.message.reply_text("👤 Enter gender for passenger 1 (Male/Female):")
    context.user_data["gender_step"] = 1
    return PRICE

async def price_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = update.message.text.capitalize()
    step = context.user_data["gender_step"]
    context.user_data["genders"].append(gender)

    if step < context.user_data["count"]:
        context.user_data["gender_step"] += 1
        await update.message.reply_text(f"👤 Enter gender for passenger {step+1} (Male/Female):")
        return PRICE

    await update.message.reply_text("💰 Enter ticket price:")
    return CONFIRM

async def confirm_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid price:")
        return CONFIRM
    context.user_data["price"] = price

    # Build ticket message
    ticket_info = (
        f"🚨 New Ticket Submitted 🚨\n\n"
        f"From: {context.user_data['from']} → To: {context.user_data['to']}\n"
        f"Date: {context.user_data['date']}\n"
        f"Train No: {context.user_data['train']}\n"
        f"Count: {context.user_data['count']}\n"
        f"Genders: {', '.join(context.user_data['genders'])}\n"
        f"💰 Price: {context.user_data['price']}\n"
    )

    # Send to group
    await context.bot.send_message(chat_id=GROUP_ID, text=ticket_info)
    await update.message.reply_text("✅ Ticket submitted successfully!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Ticket submission cancelled.")
    return ConversationHandler.END

# -------------------- MAIN --------------------
def main():
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)  # Railway safe timeouts
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, from_station),
                      CommandHandler("start", start)],
        states={
            FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_station)],
            TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, to_station)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, travel_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, train_number)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_count)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_gender)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_entry)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_ticket)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    logger.info("Bot polling starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
