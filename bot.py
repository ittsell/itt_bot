import os
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# Load from environment variables (set in Render dashboard)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))      # Example: 8238096030
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))

# Store pending requests
pending_requests = {}  # key: user_id, value: {"username": ..., "date": ..., "status": ...}
seller_phone = None


# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Buy Now", callback_data="buy_request")]]
    await update.message.reply_text(
        "Welcome! Press the button below to request a ticket.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Handle Buy Now button in group
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name

    if query.data == "buy_request":
        today = datetime.now().strftime("%d-%m-%Y")

        pending_requests[user_id] = {
            "username": username,
            "date": today,
            "status": "pending"
        }

        # Forward request to seller (hiding buyer details)
        keyboard = [
            [InlineKeyboardButton("Ticket Available ✅", callback_data=f"available_{user_id}")],
            [InlineKeyboardButton("Ticket Not Available ❌", callback_data=f"not_available_{user_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,  # For simplicity, assume admin acts as seller here
            text=(
                f"📢 New Ticket Request on {today}\n\n"
                f"Buyer details are hidden.\n\n"
                f"Please share your phone number first."
            )
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Please type your phone number (only visible to admin)."
        )

    elif query.data.startswith("available_"):
        buyer_id = int(query.data.split("_")[1])
        buyer_info = pending_requests.get(buyer_id)

        if buyer_info:
            # Send to admin for approval with phone number
            text = (
                f"✅ Ticket Confirmed Available!\n\n"
                f"👤 Buyer: {buyer_info['username']}\n"
                f"📅 Date: {buyer_info['date']}\n"
                f"📞 Seller Phone: {seller_phone or 'Not Provided'}\n\n"
                "Approve or Reject?"
            )
            keyboard = [
                [InlineKeyboardButton("Approve ✅", callback_data=f"approve_{buyer_id}")],
                [InlineKeyboardButton("Reject ❌", callback_data=f"reject_{buyer_id}")]
            ]
            await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("not_available_"):
        buyer_id = int(query.data.split("_")[1])
        if buyer_id in pending_requests:
            await context.bot.send_message(
                chat_id=buyer_id,
                text="❌ Sorry, the ticket is not available."
            )
            del pending_requests[buyer_id]

    elif query.data.startswith("approve_"):
        buyer_id = int(query.data.split("_")[1])
        if buyer_id in pending_requests:
            await context.bot.send_message(
                chat_id=buyer_id,
                text="✅ Your ticket request has been approved by the admin."
            )
            del pending_requests[buyer_id]

    elif query.data.startswith("reject_"):
        buyer_id = int(query.data.split("_")[1])
        if buyer_id in pending_requests:
            await context.bot.send_message(
                chat_id=buyer_id,
                text="❌ Your ticket request has been rejected by the admin."
            )
            del pending_requests[buyer_id]


# Collect seller phone number (only for admin)
async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global seller_phone
    if update.message.from_user.id == ADMIN_ID:
        seller_phone = update.message.text
        await update.message.reply_text(f"📞 Phone number saved (only visible to admin).")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
