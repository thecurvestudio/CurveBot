import os
import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
import requests

from dotenv import load_dotenv

from utils import validate_and_extract_urls

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
    db_get_memory_by_id,
    db_update_video_url,
    db_add_group,
    db_get_all_groups,
)

from vidu import reference_to_video, get_generation_status


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

USE_MOCK_DATA = False
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
POLL_SLEEP_CYCLE_SECONDS = 5  # seconds
MAX_POLLING_TIME_SECONDS = 60  # seconds


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = context.bot.username  # Get the bot's username dynamically
    commands = f"""
*Available user commands:*
/start - Show this help message
/imagine <prompt> - Generate a video based on the group's reference
/memory <id:optional> - Show your last 5 generated videos or a specific video by ID

*Available admin commands:*
/reference <value> or <file.txt> - Set a reference for the group
File has to be a .txt file with a list of URLs, one URL per line
/sgl <value> - Set a monthly limit for the group
/sul <value> - Set a monthly limit for all users in the group
/groups - Show all groups where the bot is added

*Note:* Use commands like `/start@{bot_username}` in group chats to explicitly target this bot.
"""
    await update.message.reply_text(commands, parse_mode="Markdown")


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
        /reference [group_id] <url1> <url2> ...
    """

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You don't have permission to set a reference.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /reference [group_id] <url1> <url2> ..."
        )
        return

    # Check if the first argument is a group ID
    try:
        group_id = int(context.args[0])
        urls = context.args[1:]  # Remaining arguments are URLs
    except ValueError:
        group_id = update.effective_chat.id  # Use the current group's ID
        urls = context.args  # All arguments are URLs

    if not urls:
        await update.message.reply_text("Please provide at least one URL.")
        return

    # Validate and join URLs
    ref = " ".join(urls)
    print(f"Group ID: {group_id}, Reference: {ref}")
    db_add_reference(group_id, ref)

    await update.message.reply_text(f"Reference for group {group_id} set to:\n{ref}")


async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You don't have permission to upload files.")
        return

    if update.message.document and update.message.document.mime_type == "text/plain":
        print("Received a .txt file")
        document = update.message.document
        caption = update.message.caption
        print(caption)
        cap_split = caption.split(" ", 1) if caption else []

        group_id = update.effective_chat.id

        if len(cap_split) == 2:
            command = cap_split[0].strip().lower()
            group_id = cap_split[1].strip()

            try:
                group_id = int(group_id)
            except ValueError:
                await update.message.reply_text(
                    "Invalid group ID. Please provide a valid numeric group ID."
                )
                return
        else:
            command = caption.strip().lower() if caption else ""
        print(f"cap_split: {cap_split}")

        if caption and command == "/reference":
            file = await context.bot.get_file(document.file_id)
            folder_path = "references"
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            file_path = f"{folder_path}/{group_id}_{document.file_name}"

            # Download the file
            await file.download_to_drive(file_path)

            # Validate and extract URLs
            urls = validate_and_extract_urls(file_path)
            if urls is None:
                await update.message.reply_text(
                    "The file must contain a valid list of URLs."
                )
                return

            # Save the URLs as a reference
            db_add_reference(group_id, ",".join(urls))
            await update.message.reply_text(
                f"Reference set from uploaded file:\n{', '.join(urls)}"
            )
        else:
            await update.message.reply_text(
                "If you want to upload a reference, please provide a valid caption (i.e., '/reference') with the file."
            )
    else:
        await update.message.reply_text("Please upload a valid .txt file.")


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
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /imagine <prompt>")
        return

    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    group_limit, user_limit = db_get_limits(group_id)
    group_usage, user_usage = db_get_usage(group_id, user_id)

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
            mock=USE_MOCK_DATA,
            api_key=API_KEY,
            model=MODEL,
            images=[ref],
            prompt=f"{user_prompt}, {ENDING_PROMPT}",
            duration=DURATION,
            aspect_ratio=ASPECT_RATIO,
            resolution=RESOLUTION,
        )
        print(f"Response is: {response}")
    except requests.exceptions.HTTPError as e:
        await update.message.reply_text(f"Error: {e}")
        return

    task_id = response.get("task_id")
    status = response.get("state")

    if not task_id:
        await update.message.reply_text("Failed to create video generation task.")
        return

    if status == "created":
        db_add_memory(
            user_id=user_id,
            group_id=group_id,
            video_url="",
            task_id=task_id,
            status="pending",
        )
        await update.message.reply_text("Generating video...")

    # Poll the API for the task status
    for _ in range(MAX_POLLING_TIME_SECONDS // POLL_SLEEP_CYCLE_SECONDS):
        status_response = get_generation_status(
            mock=USE_MOCK_DATA, api_key=API_KEY, task_id=task_id
        )
        state = status_response.get("state")

        if state == "success":
            creations = status_response.get("creations", [])
            if creations:
                video_url = creations[0].get("url")
                await update.message.reply_video(video=video_url)
                db_update_usage(group_id, user_id)
                db_update_video_url(user_id, group_id, task_id, video_url)
            else:
                await update.message.reply_text("No video URL found in the response.")
            return
        elif state == "failed":
            await update.message.reply_text("Video generation failed.")
            return

        await asyncio.sleep(POLL_SLEEP_CYCLE_SECONDS)

    await update.message.reply_text(
        "Video generation is taking too long. Use /memory <id> to check the status."
    )


async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if an ID is passed as an argument
    if context.args:
        try:
            memory_id = int(context.args[0])  # Parse the ID
        except ValueError:
            await update.message.reply_text(
                "Invalid ID. Please provide a valid numeric ID."
            )
            return

        # Fetch specific memory by ID
        memory = db_get_memory_by_id(user_id, group_id, memory_id)

        if not memory:
            await update.message.reply_text(f"No memory found with ID {memory_id}.")
            return

        url, ts, task_id, status = memory

        # Poll the API for the task status
        if status == "pending":
            await update.message.reply_text("Video is still being generated.")
            for _ in range(MAX_POLLING_TIME_SECONDS // POLL_SLEEP_CYCLE_SECONDS):
                status_response = get_generation_status(
                    mock=USE_MOCK_DATA, api_key=API_KEY, task_id=task_id
                )
                state = status_response.get("state")

                if state == "success":
                    creations = status_response.get("creations", [])
                    if creations:
                        video_url = creations[0].get("url")
                        db_update_usage(group_id, user_id)
                        db_update_video_url(
                            user_id, group_id, task_id, video_url, status="success"
                        )
                        await update.message.reply_video(video=video_url)
                    else:
                        await update.message.reply_text(
                            "No video URL found in the response."
                        )
                    return
                elif state == "failed":
                    await update.message.reply_text("Video generation failed.")
                    return

                await asyncio.sleep(POLL_SLEEP_CYCLE_SECONDS)
            await update.message.reply_text(
                "Video generation is taking too long. Use /memory <id> to check the status."
            )
            return
        elif status == "success":
            await update.message.reply_video(video=url)
            return

        await update.message.reply_text(f"Generated at {ts} UTC:\n{url}")
        return

    # Fetch the last 5 memories if no ID is provided
    history = db_get_memory(user_id, group_id)
    if not history:
        await update.message.reply_text("No past videos found.")
        return

    # Combine all rows into a single message
    message = f"Here are your last {len(history)} generated videos:\n\n"
    for video_id, url, ts in history:
        formatted_ts = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        message += f"ID: {video_id} - Generated at {formatted_ts}\n"
    message += "\nUse /memory <id> to view a specific video."
    await update.message.reply_text(message)


async def get_tracked_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Display all groups where the bot is added.

    Args:
        update (Update): The incoming update from the Telegram bot.
        context (ContextTypes.DEFAULT_TYPE): The context for the command.
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "You don't have permission to view this information."
        )
        return

    groups = db_get_all_groups()
    if not groups:
        await update.message.reply_text("No groups found.")
        return

    message = "Here are the groups where the bot is added:\n\n"
    for group_id, group_name in groups:
        message += f"Name: {group_name}\nID: {group_id}\n\n"

    await update.message.reply_text(message)


async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the event when the bot is added to a group.

    Args:
        update (Update): The incoming update from the Telegram bot.
        context (ContextTypes.DEFAULT_TYPE): The context for the event.
    """
    chat_member = update.my_chat_member
    if chat_member.new_chat_member.status == "member":  # Bot is added to the group
        group_id = chat_member.chat.id
        group_name = chat_member.chat.title
        print(f"Bot added to group: {group_name} (ID: {group_id})")

        # Track the group in the database
        if group_name:  # Only track groups, not private chats
            db_add_group(group_id, group_name)
            await context.bot.send_message(
                chat_id=group_id,
                text=f"Hello! I've been added to {group_name}.",
            )


if __name__ == "__main__":
    print("Running CurveBot...")
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the Telegram bot.")
    parser.add_argument(
        "--mockdata",
        action="store_true",
        help="Use mock data instead of connecting to external APIs.",
    )
    args = parser.parse_args()

    # Check if mock data is enabled
    USE_MOCK_DATA = args.mockdata

    # --- Bot Init ---
    init_db()
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reference", reference))
    app.add_handler(CommandHandler("sgl", set_group_limit))
    app.add_handler(CommandHandler("sul", set_user_limit))
    app.add_handler(CommandHandler("imagine", imagine))
    app.add_handler(CommandHandler("memory", memory))
    app.add_handler(CommandHandler("groups", get_tracked_groups))
    app.add_handler(MessageHandler(filters.Document.TEXT, handle_file_upload))
    app.add_handler(
        ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.run_polling()
