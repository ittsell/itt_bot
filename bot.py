import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Configuration ----------------
BOT_TOKEN = "7423784466:AAE_IDLMRaNF-gZQ673ROVKeqO7day86SKo"
GROUP_CHAT_ID = -1001234567890       # Replace with your group chat ID
ADMIN_ID = 8238096030                # Replace with your admin ID

# Store pending requests: {user_id: {"chat_id": ..., "username": ..., "ticket_id": ..., "timeout_task": ...}}
pending_requests = {}


# ---------------- Start Command ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Press 'Buy Now' to request a ticket.")


# ---------------- Handle Buy Now ----------------
async def buy_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ticket_id = f"TICKET-{int(datetime.now().timestamp())}"

    pending_requests[user.id] = {
        "chat_id": update.effective_chat.id,
        "username": user.username or user.first_name,
        "ticket_id": ticket_id,
    }

    # Cancel Button for user
    keyboard = [[InlineKeyboardButton("❌ Cancel Request", callback_data=f"cancel_{user.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"📢 New request from @{user.username or user.first_name} (hidden from seller)\nTicket ID: {ticket_id}\n\nSeller, is this ticket available?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Available", callback_data=f"available_{user.id}"),
                InlineKeyboardButton("❌ Sold", callback_data=f"sold_{user.id}")
            ]
        ])
    )

    await update.message.reply_text("Your request has been forwarded. You can cancel anytime.", reply_markup=reply_markup)

    # Start auto-timeout task
    pending_requests[user.id]["timeout_task"] = asyncio.create_task(drop_after_timeout(user.id, context))


# ---------------- Cancel Request ----------------
async def cancel_request(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    if user_id in pending_requests:
        ticket_id = pending_requests[user_id]["ticket_id"]
        del pending_requests[user_id]

        # Notify group (seller side)
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"❌ Request {ticket_id} has been cancelled by the user."
        )

        # Notify user
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Your request {ticket_id} has been cancelled."
        )


# ---------------- Drop after timeout ----------------
async def drop_after_timeout(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(300)  # 5 minutes
    if user_id in pending_requests:
        ticket_id = pending_requests[user_id]["ticket_id"]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⚠️ No update received for {ticket_id}. Chat closed automatically."
        )
        del pending_requests[user_id]


# ---------------- Handle Buttons ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = int(data.split("_")[1])

    if data.startswith("cancel_"):
        await cancel_request(user_id, context)

    elif data.startswith("available_"):
        if user_id in pending_requests:
            ticket_id = pending_requests[user_id]["ticket_id"]

            # Forward request to Admin only
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📩 Ticket available for ID {ticket_id}. Approve?",
                reply_markup=reply_markup
            )

            # Ask seller for phone number (admin-only visible)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📞 Please provide phone number for Ticket {ticket_id}."
            )

    elif data.startswith("sold_"):
        if user_id in pending_requests:
            ticket_id = pending_requests[user_id]["ticket_id"]

            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Sorry, ticket {ticket_id} is already sold."
            )

            del pending_requests[user_id]

    elif data.startswith("approve_"):
        if user_id in pending_requests:
            ticket_id = pending_requests[user_id]["ticket_id"]

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Your request {ticket_id} has been approved by Admin."
            )

            del pending_requests[user_id]

    elif data.startswith("reject_"):
        if user_id in pending_requests:
            ticket_id = pending_requests[user_id]["ticket_id"]

            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Your request {ticket_id} was rejected by Admin."
            )

            del pending_requests[user_id]


# ---------------- Main ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buy_now))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
