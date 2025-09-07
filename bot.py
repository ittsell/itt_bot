# bot.py
import os
import logging
from datetime import datetime, date
from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest
import uuid

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")  # string; convert to int
ADMIN_ID = int(os.getenv("ADMIN_ID", "8238096030"))
PORT = int(os.getenv("PORT", "8443"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")

if not BOT_TOKEN or not GROUP_CHAT_ID:
    raise SystemExit("BOT_TOKEN and GROUP_CHAT_ID are required!")

GROUP_CHAT_ID = int(GROUP_CHAT_ID)
if not WEBHOOK_PATH:
    WEBHOOK_PATH = BOT_TOKEN.split(":")[0]

# ---------- logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- conversation states ----------
COUNT, SRC_NAME, SRC_CODE, DEST_NAME, DEST_CODE, DATE_S, TRAIN, GENDER, CLASS, PRICE, PHONE, CONFIRM = range(12)

# ---------- helpers ----------
def parse_date_dd_mm_yyyy(s: str):
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
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
    await update.message.reply_text("Enter Source station name (e.g., Chennai):")
    return SRC_NAME

async def ask_src_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source_name"] = update.message.text.strip()
    await update.message.reply_text("Enter Source station code (e.g., MAS):")
    return SRC_CODE

async def ask_src_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source_code"] = update.message.text.strip().upper()
    await update.message.reply_text("Enter Destination station name (e.g., Trivandrum):")
    return DEST_NAME

async def ask_dest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dest_name"] = update.message.text.strip()
    await update.message.reply_text("Enter Destination station code (e.g., TVC):")
    return DEST_CODE

async def ask_dest_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dest_code"] = update.message.text.strip().upper()
    await update.message.reply_text("Enter Journey date (DD-MM-YYYY):")
    return DATE_S

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    d = parse_date_dd_mm_yyyy(txt)
    if not d:
        await update.message.reply_text("Invalid date format. Use DD-MM-YYYY (e.g., 29-10-2025). Try again:")
        return DATE_S
    if d < date.today():
        await update.message.reply_text("Date cannot be in the past. Enter a future date (DD-MM-YYYY):")
        return DATE_S
    context.user_data["date"] = d.strftime("%d-%m-%Y")
    await update.message.reply_text("Enter Train number (e.g., 16605):")
    return TRAIN

async def ask_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["train"] = update.message.text.strip()
    await update.message.reply_text(f"Enter gender of passenger 1 (Male/Female/Other):")
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
    kb = [["Sleeper", "3A", "2A", "1A", "2S"]]
    await update.message.reply_text("Select Ticket class:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))
    return CLASS

async def ask_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["class"] = update.message.text.strip()
    await update.message.reply_text("Enter total ticket price (in ₹):", reply_markup=ReplyKeyboardRemove())
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
    await update.message.reply_text("Enter your phone number (visible to admin only):")
    return PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data["phone"] = txt
    # Prepare confirmation
    info = context.user_data
    ticket_id = str(uuid.uuid4())[:8].upper()
    context.user_data["ticket_id"] = ticket_id

    summary = (
        f"🎫 Ticket ID: {ticket_id}\n"
        f"🚉 {info['source_name']}({info['source_code']}) → {info['dest_name']}({info['dest_code']})\n"
        f"📅 {info['date']} | 🚆 {info['train']} | Class: {info['class']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n\n"
        "Reply YES to post to the group, or NO to cancel."
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
    ticket_id = info["ticket_id"]
    # Post to group
    kb = [
        [InlineKeyboardButton("Buy Now", callback_data=f"buy_{ticket_id}"), 
         InlineKeyboardButton("Cancel Request", callback_data=f"cancel_{ticket_id}")]
    ]
    post = (
        f"🎫 Ticket ID: {ticket_id}\n"
        f"🚉 {info['source_name']}({info['source_code']}) → {info['dest_name']}({info['dest_code']})\n"
        f"📅 {info['date']} | 🚆 {info['train']} | Class: {info['class']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n"
        f"Status: Available"
    )
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post, reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.exception("Failed to post to group: %s", e)
        await update.message.reply_text("Failed to post to group. Ensure the bot is added and has permission.")
        return ConversationHandler.END

    # Send seller phone only to admin
    admin_msg = f"Seller phone for ticket {ticket_id}: {info['phone']}"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
    except:
        pass

    await update.message.reply_text("✅ Your ticket has been posted to the group.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- button callback handler ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("buy_"):
        ticket_id = data.split("_")[1]
        # send request to seller (hide buyer details)
        seller_msg = f"Buyer requested Ticket ID: {ticket_id}. Confirm availability."
        await context.bot.send_message(chat_id=ADMIN_ID, text=seller_msg)
        await query.edit_message_text(text=f"{query.message.text}\n\n🛒 Buy request sent to seller.")
    elif data.startswith("cancel_"):
        ticket_id = data.split("_")[1]
        await query.edit_message_text(text=f"{query.message.text}\n\n❌ Buy request canceled.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- main ----------
def main():
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("sell", sell_entry), MessageHandler(filters.Regex("^(Sell Ticket)$") & ~filters.COMMAND, sell_entry), CommandHandler("start", start)],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_count)],
            SRC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_src_name)],
            SRC_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_src_code)],
            DEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest_name)],
            DEST_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest_code)],
            DATE_S: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_train)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_class)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_post)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="sell_conv",
        persistent=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Starting bot. WEBHOOK_URL=%s, PATH=%s, PORT=%s", WEBHOOK_URL, WEBHOOK_PATH, PORT)

    if WEBHOOK_URL:
        webhook_url = WEBHOOK_URL.rstrip("/") + "/" + WEBHOOK_PATH
        logger.info("Running webhook: %s", webhook_url)
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=WEBHOOK_PATH, webhook_url=webhook_url)
    else:
        logger.info("No WEBHOOK_URL; running long-polling (local dev).")
        app.run_polling()

if __name__ == "__main__":
    main()
