import asyncio

from pyrogram import Client, filters



# =========================
# GLOBAL CANCEL EVENTS
# =========================

cancel_events = {}


def get_cancel_event(user_id):
    event = cancel_events.get(user_id)

    if event is None:
        event = asyncio.Event()
        cancel_events[user_id] = event

    return event


def clear_cancel_event(user_id):
    cancel_events.pop(user_id, None)


def cancel_user(user_id):
    event = get_cancel_event(user_id)
    event.set()


def is_cancelled(user_id):
    event = cancel_events.get(user_id)
    return bool(event and event.is_set())


# =========================
# /CANCEL
# =========================

@Client.on_message(
    filters.command("cancel")
    & filters.private
)
async def cancel_command(client, message):

    user_id = message.from_user.id

    event = cancel_events.get(user_id)

    if not event:
        await message.reply_text(
            "ℹ️ No active operation to cancel."
        )
        return

    if event.is_set():
        await message.reply_text(
            "⏳ Cancellation is already in progress..."
        )
        return

    event.set()

    await message.reply_text(
        "🛑 Cancellation requested.\n\n"
        "The current operation will stop shortly."
    )
