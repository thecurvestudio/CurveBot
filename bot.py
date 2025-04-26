import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import requests

from dotenv import load_dotenv

load_dotenv()

from services import (
    init_db,
    db_get_reference,
    db_add_reference,
    db_get_limits,
    db_get_usage,
    db_update_usage,
    db_add_memory,
    db_get_memory,
    db_set_group_limit,
    db_set_user_limit,
)

from vidu import reference_to_video, get_generation_status


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


ADMIN_ID = int(os.getenv("ADMIN_ID"))
API_KEY = os.getenv("VIDO_API_KEY")
VIDU_API_URL = "https://api.vidu.com/imagine"
MODEL = "vidu1.5"
IMAGES = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Leonardo_Dicaprio_Cannes_2019.jpg/250px-Leonardo_Dicaprio_Cannes_2019.jpg"
]
ASPECT_RATIO = "16:9"
RESOLUTION = "360p"
DURATION = 4
ENDING_PROMPT = "2d animation"
POLL_SLEEP_CYCLE = 5  # seconds
MAX_POLLING_TIME = 60  # seconds


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
Available commands:
/start - Show this help message
/reference <value> - Set a reference for the group
/imagine - Generate a video based on the group's reference
/memory - Show your last 5 generated videos
"""
    await update.message.reply_text(commands)



async def reference(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /reference command to set a reference for the group.

    Args:
        update (Update): The incoming update from the Telegram bot.
        context (ContextTypes.DEFAULT_TYPE): The context for the command, including arguments.

    Behavior:
        - Checks if the user has admin permissions.
        - Validates that a reference value is provided.
        - Saves the reference for the group in the database.
        - Sends a confirmation message with the reference.

    Usage:
        /reference <value>
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You don't have permission to set a reference.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /reference <value>")
        return
    group_id = update.effective_chat.id
    ref = " ".join(context.args)

    db_add_reference(group_id, ref)

    await update.message.reply_text(f"Reference for this group set to:\n{ref}")


async def set_group_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /sgl command to set a monthly limit for the group.

    Args:
        update (Update): The incoming update from the Telegram bot.
        context (ContextTypes.DEFAULT_TYPE): The context for the command, including arguments.

    Behavior:
        - Checks if the user has admin permissions.
        - Validates that a single argument (the group limit) is provided.
        - Parses the group limit as an integer.
        - Updates the group limit in the database.
        - Sends a confirmation message with the new group limit.

    Usage:
        /sgl <value>
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "You don't have permission to set group limits."
        )
        return
    group_id = update.effective_chat.id

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /sgl <value>")
        return

    try:
        group_limit = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /sgl <value>")
        return
    db_set_group_limit(group_id, group_limit)
    await update.message.reply_text(f"Group limit set to {group_limit} per month")


async def set_user_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /sul command to set a monthly limit for individual users in the group.

    Args:
        update (Update): The incoming update from the Telegram bot.
        context (ContextTypes.DEFAULT_TYPE): The context for the command, including arguments.

    Behavior:
        - Checks if the user has admin permissions.
        - Validates that a single argument (the user limit) is provided.
        - Parses the user limit as an integer.
        - Updates the user limit in the database.
        - Sends a confirmation message with the new user limit.

    Usage:
        /sul <value>
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You don't have permission to set user limits.")
        return
    group_id = update.effective_chat.id

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /sul <value>")
        return

    try:
        user_limit = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /sul <value>")
        return

    db_set_user_limit(group_id, user_limit)
    await update.message.reply_text(f"User limit set to {user_limit} per month")


async def imagine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    group_limit, user_limit = db_get_limits(group_id)
    group_usage, user_usage = db_get_usage(group_id, user_id)
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /imagine <prompt>")
        return
    if group_limit is not None and group_usage >= group_limit:
        await update.message.reply_text("Group has reached its monthly limit.")
        return
    if user_limit is not None and user_usage >= user_limit:
        await update.message.reply_text("You have reached your monthly limit.")
        return

    ref = db_get_reference(group_id)
    if not ref:
        await update.message.reply_text("No reference set for this group.")
        return

    # Call the reference_to_video function to start the task
    user_prompt = " ".join(context.args)

    try:
        response = reference_to_video(
            api_key=API_KEY,
            model=MODEL,
            images=IMAGES,  # TODO Replace with actual images i.e. REF
            prompt=f"{user_prompt}, {ENDING_PROMPT}",
            duration=DURATION,
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
        )
    except requests.exceptions.HTTPError as e:
        await update.message.reply_text(f"Error: {e}")
        return

    task_id = response.get("task_id")
    status = response.get("state")

    if not task_id:
        await update.message.reply_text("Failed to create video generation task.")
        return

    if status == "created":
        await update.message.reply_text("Generating video...")

    # Poll the API for the task status
    for _ in range(MAX_POLLING_TIME // POLL_SLEEP_CYCLE):
        status_response = get_generation_status(api_key=API_KEY, task_id=task_id)
        state = status_response.get("state")

        if state == "success":
            creations = status_response.get("creations", [])
            if creations:
                video_url = creations[0].get("url")
                await update.message.reply_video(video=video_url)
                db_update_usage(group_id, user_id)
                db_add_memory(user_id, video_url)
            else:
                await update.message.reply_text("No video URL found in the response.")
            return
        elif state == "failed":
            await update.message.reply_text("Video generation failed.")
            return

        await asyncio.sleep(POLL_SLEEP_CYCLE)

    await update.message.reply_text(
        "Video generation is taking too long. Please try again later."
    )



async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = db_get_memory(user_id)
    if not history:
        await update.message.reply_text("No past videos found.")
        return
    for url, ts in history:
        await update.message.reply_text(f"Generated at {ts} UTC:\n{url}")


# --- Bot Init ---
init_db()
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reference", reference))
app.add_handler(CommandHandler("sgl", set_group_limit))
app.add_handler(CommandHandler("sul", set_user_limit))
app.add_handler(CommandHandler("imagine", imagine))
app.add_handler(CommandHandler("memory", memory))

if __name__ == "__main__":
    app.run_polling()
