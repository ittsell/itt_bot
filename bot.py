# ---------- button callback handler ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("buy_"):
        ticket_id = data.split("_")[1]

        # notify seller (instead of admin directly)
        seller_msg = (
            f"📢 You have a new buy request for Ticket ID: {ticket_id}.\n"
            f"Please confirm availability."
        )
        kb = [
            [InlineKeyboardButton("✅ Available", callback_data=f"avail_{ticket_id}")],
            [InlineKeyboardButton("❌ Already Sold", callback_data=f"sold_{ticket_id}")]
        ]

        # For now, we assume seller is the one who posted (stored in context?)
        # Let's send to ADMIN_ID as proxy for seller until seller IDs are stored
        await context.bot.send_message(chat_id=ADMIN_ID, text=seller_msg, reply_markup=InlineKeyboardMarkup(kb))

        # Update group post
        await query.edit_message_text(text=f"{query.message.text}\n\n🛒 Buy request sent to seller.")

    elif data.startswith("avail_"):
        ticket_id = data.split("_")[1]

        # forward request to admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 Ticket ID {ticket_id} marked AVAILABLE by seller.\nWaiting for your approval."
        )

        await query.edit_message_text(text=f"Ticket ID {ticket_id} marked ✅ Available. Sent to Admin.")

    elif data.startswith("sold_"):
        ticket_id = data.split("_")[1]

        # notify in group
        await query.edit_message_text(text=f"Ticket ID {ticket_id} marked ❌ Already Sold.")
        
        # Optionally notify buyer privately if needed
