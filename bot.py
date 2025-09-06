# bot.py
import os
import json
import logging
from datetime import datetime, date
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8238096030"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
PORT = int(os.getenv("PORT", "8443"))

if not BOT_TOKEN or not GROUP_CHAT_ID:
    raise SystemExit("BOT_TOKEN and GROUP_CHAT_ID are required.")

if not WEBHOOK_PATH:
    WEBHOOK_PATH = BOT_TOKEN.split(":")[0]

# ---------- logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- conversation states ----------
COUNT, SOURCE, SOURCE_CODE, DEST, DEST_CODE, DATE_S, TRAIN, CLASS, GENDER, PRICE, CONFIRM = range(11)

# ---------- ticket storage ----------
TICKET_FILE = "tickets.json"
tickets = {}
if os.path.exists(TICKET_FILE):
    with open(TICKET_FILE, "r") as f:
        tickets = json.load(f)

def save_tickets():
    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=2)

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

def generate_ticket_id():
    return str(max([int(k) for k in tickets.keys()], default=0) + 1)

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
    return SOURCE

async def ask_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source"] = update.message.text.strip()
    await update.message.reply_text("Enter Source station code (e.g., MAS):")
    return SOURCE_CODE

async def ask_source_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["source_code"] = update.message.text.strip().upper()
    await update.message.reply_text("Enter Destination station name (e.g., Trivandrum):")
    return DEST

async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dest"] = update.message.text.strip()
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
    await update.message.reply_text("Enter ticket class (Sleeper, 3A, 2A, 1A, 2S):")
    return CLASS

async def ask_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cls = update.message.text.strip().upper()
    if cls not in ["SLEEPER","3A","2A","1A","2S"]:
        await update.message.reply_text("Invalid class. Choose from Sleeper, 3A, 2A, 1A, 2S:")
        return CLASS
    context.user_data["class"] = cls
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
    await update.message.reply_text("Enter total ticket price (in ₹):")
    return PRICE

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        price = float(txt)
        if price < 0: raise ValueError
    except:
        await update.message.reply_text("Invalid price. Enter a numeric value (e.g., 1200).")
        return PRICE
    context.user_data["price"] = price

    # generate ticket id
    ticket_id = generate_ticket_id()
    context.user_data["ticket_id"] = ticket_id

    info = context.user_data
    summary = (
        f"Please confirm your ticket:\n\n"
        f"Ticket ID: {ticket_id}\n"
        f"From: {info['source']} ({info['source_code']}) → {info['dest']} ({info['dest_code']})\n"
        f"Date: {info['date']} | Train: {info['train']} | Class: {info['class']}\n"
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
    ticket_id = info["ticket_id"]

    post_text = (
        f"🎫 New Ticket Available 🎫\n\n"
        f"Ticket ID: {ticket_id}\n"
        f"🚉 {info['source']} ({info['source_code']}) → {info['dest']} ({info['dest_code']})\n"
        f"📅 {info['date']} | 🚆 {info['train']} | Class: {info['class']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n"
    )

    keyboard = [[InlineKeyboardButton("Buy Now", callback_data=f"buy_{ticket_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        message = await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post_text, reply_markup=reply_markup)
        # save ticket
        tickets[ticket_id] = {
            "info": info,
            "status": "Available",
            "message_id": message.message_id
        }
        save_tickets()
    except Exception as e:
        logger.exception("Failed to post to group: %s", e)
        await update.message.reply_text("Failed to post to group. Ensure the bot is added to the group and has message permissions.")
        return ConversationHandler.END

    await update.message.reply_text("✅ Your ticket has been posted to the group.")
    context.user_data.clear()
    return ConversationHandler.END

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("buy_"):
        ticket_id = data.split("_")[1]
        if ticket_id in tickets:
            info = tickets[ticket_id]["info"]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"User @{query.from_user.username} wants to buy ticket {ticket_id}.\nDetails: {info}"
            )
            await query.message.reply_text("Admin has been notified. They will contact you.")

async def mark_sold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sold <ticket_id>")
        return
    ticket_id = args[0]
    if ticket_id not in tickets:
        await update.message.reply_text("Ticket ID not found.")
        return
    tickets[ticket_id]["status"] = "Sold"
    save_tickets()
    # update group message
    info = tickets[ticket_id]["info"]
    text = (
        f"🎫 Ticket Sold 🎫\n\n"
        f"Ticket ID: {ticket_id}\n"
        f"🚉 {info['source']} ({info['source_code']}) → {info['dest']} ({info['dest_code']})\n"
        f"📅 {info['date']} | 🚆 {info['train']} | Class: {info['class']}\n"
        f"🧾 Tickets: {info['count']} | Genders: {', '.join(info['genders'])}\n"
        f"💰 Price: ₹{info['price']}\n"
        f"❌ SOLD"
    )
    try:
        await context.bot.edit_message_text(
            chat_id=GROUP_CHAT_ID,
            message_id=tickets[ticket_id]["message_id"],
            text=text
        )
        await update.message.reply_text(f"Ticket {ticket_id} marked as sold.")
    except Exception as e:
        logger.exception("Failed to update group message: %s", e)
        await update.message.reply_text("Failed to update group message.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ---------- main ----------
def main():
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("sell", sell_entry),
            MessageHandler(filters.Regex("^(Sell Ticket)$") & ~filters.COMMAND, sell_entry),
            CommandHandler("start", start)
        ],
        states={
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_count)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_source)],
            SOURCE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_source_code)],
            DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            DEST_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest_code)],
            DATE_S: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TRAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_train)],
            CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_class)],
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
    app.add_handler(CallbackQueryHandler(buy_callback))
    app.add_handler(CommandHandler("sold", mark_sold))

    logger.info("Starting bot. WEBHOOK_URL=%s, PATH=%s, PORT=%s", WEBHOOK_URL, WEBHOOK_PATH, PORT)

    if WEBHOOK_URL:
        webhook_url = WEBHOOK_URL.rstrip("/") + "/" + WEBHOOK_PATH
        logger.info("Running webhook: %s", webhook_url)
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=WEBHOOK_PATH, webhook_url=webhook_url)
    else:
        logger.info("No WEBHOOK_URL provided; running long-polling (local dev).")
        app.run_polling()

if __name__ == "__main__":
    main()
