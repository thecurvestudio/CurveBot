import os
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_db_path():
    return os.getenv("DATABASE", "bot_data.db")


def init_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_name TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS prompts (
        group_id INTEGER PRIMARY KEY,
        prompt TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS usage (
        group_id INTEGER,
        user_id INTEGER,
        month TEXT,
        group_calls INTEGER DEFAULT 0,
        user_calls INTEGER DEFAULT 0,
        PRIMARY KEY (group_id, user_id, month)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS limits (
        group_id INTEGER PRIMARY KEY,
        group_limit INTEGER,
        user_limit INTEGER
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS memory (
        user_id INTEGER,
        group_id INTEGER,
        video_url TEXT,
        timestamp TEXT,
        task_id TEXT,
        status TEXT,
        user_video_id INTEGER
    )"""
    )
    conn.commit()
    conn.close()


def get_db_connection():
    """
    Get a get_db_path() connection.

    Returns:
        sqlite3.Connection: A connection object to the get_db_path().
    """
    return sqlite3.connect(get_db_path())


def db_get_month():
    """
    Get the current month in the format 'YYYY-MM'.

    Returns:
        str: The current month as a string.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m")


def db_get_reference(group_id):
    """
    Retrieve the reference text for a specific group.

    Args:
        group_id (int): The ID of the group.

    Returns:
        str or None: The reference text if it exists, otherwise None.
    """

    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT prompt FROM prompts WHERE group_id = ?", (group_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def db_add_reference(group_id, ref):
    """
    Add or update the reference text for a specific group.

    Args:
        group_id (int): The ID of the group.
        ref (str): The reference text to set.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO prompts (group_id, prompt) VALUES (?, ?)",
        (group_id, ref),
    )
    conn.commit()
    conn.close()


def db_update_usage(group_id, user_id):
    """
    Update the usage statistics for a specific group and user.

    Args:
        group_id (int): The ID of the group.
        user_id (int): The ID of the user.
    """
    month = db_get_month()
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        """INSERT OR IGNORE INTO usage (group_id, user_id, month) VALUES (?, ?, ?)""",
        (group_id, user_id, month),
    )
    c.execute(
        """UPDATE usage SET group_calls = group_calls + 1, user_calls = user_calls + 1 WHERE group_id = ? AND user_id = ? AND month = ?""",
        (group_id, user_id, month),
    )
    conn.commit()
    conn.close()


def db_get_limits(group_id):
    """
    Retrieve the group and user limits for a specific group.

    Args:
        group_id (int): The ID of the group.

    Returns:
        tuple: A tuple containing the group limit and user limit, or (None, None) if not set.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT group_limit, user_limit FROM limits WHERE group_id = ?", (group_id,)
    )
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)


def db_set_group_limit(group_id, group_limit):
    """
    Set or update the group limit for a specific group.

    Args:
        group_id (int): The ID of the group.
        group_limit (int): The group limit to set.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO limits (group_id, group_limit, user_limit) VALUES (?, ?, COALESCE((SELECT user_limit FROM limits WHERE group_id = ?), NULL))",
        (group_id, group_limit, group_id),
    )
    conn.commit()
    conn.close()


def db_set_user_limit(group_id, user_limit):
    """
    Set or update the user limit for a specific group.

    Args:
        group_id (int): The ID of the group.
        user_limit (int): The user limit to set.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO limits (group_id, group_limit, user_limit) VALUES (?, COALESCE((SELECT group_limit FROM limits WHERE group_id = ?), NULL), ?)",
        (group_id, group_id, user_limit),
    )
    conn.commit()
    conn.close()


def db_get_usage(group_id, user_id):
    """
    Retrieve the usage statistics for a specific group and user.

    Args:
        group_id (int): The ID of the group.
        user_id (int): The ID of the user.

    Returns:
        tuple: A tuple containing the group calls and user calls, or (0, 0) if no usage exists.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT group_calls, user_calls FROM usage WHERE group_id = ? AND user_id = ? AND month = ?",
        (group_id, user_id, db_get_month()),
    )
    row = c.fetchone()
    conn.close()
    return row if row else (0, 0)


def db_add_memory(user_id, group_id, video_url, task_id, status="pending"):
    """
    Add a video URL to the memory table for a specific user.

    Args:
        user_id (int): The ID of the user.
        group_id (int): The ID of the group.
        video_url (str): The URL of the video to add.
        task_id (str): The task ID associated with the video.
        status (str): The status of the task (default is "pending").
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # Calculate the next user_video_id
    c.execute(
        "SELECT COALESCE(MAX(user_video_id), 0) + 1 FROM memory WHERE user_id = ? AND group_id = ?",
        (user_id, group_id),
    )
    next_user_video_id = c.fetchone()[0]

    # Insert the new record
    c.execute(
        "INSERT INTO memory (user_id, group_id, video_url, timestamp, task_id, status, user_video_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            group_id,
            video_url,
            datetime.now(timezone.utc),
            task_id,
            status,
            next_user_video_id,
        ),
    )
    conn.commit()
    conn.close()


def db_update_video_url(user_id, group_id, task_id, video_url, status="success"):
    """
    Update the video URL in the memory table for a specific user and task.

    Args:
        user_id (int): The ID of the user.
        group_id (int): The ID of the group.
        task_id (str): The task ID associated with the video.
        video_url (str): The new video URL to update.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "UPDATE memory SET video_url = ?, status = ? WHERE user_id = ? AND group_id = ? AND task_id = ?",
        (video_url, status, user_id, group_id, task_id),
    )
    conn.commit()
    conn.close()


def db_update_status(user_id, group_id, task_id, status):
    """
    Update the status in the memory table for a specific user and task.

    Args:
        user_id (int): The ID of the user.
        group_id (int): The ID of the group.
        task_id (str): The task ID associated with the video.
        status (str): The new status to update.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "UPDATE memory SET status = ? WHERE user_id = ? AND group_id = ? AND task_id = ?",
        (status, user_id, group_id, task_id),
    )
    conn.commit()
    conn.close()


def db_get_memory(user_id, group_id):
    """
    Retrieve the last 5 video URLs from the memory table for a specific user.

    Args:
        user_id (int): The ID of the user.
        group_id (int): The ID of the group.

    Returns:
        list: A list of tuples containing video URLs and timestamps.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT user_video_id, video_url, timestamp FROM memory WHERE user_id = ? AND group_id = ? ORDER BY timestamp DESC LIMIT 5",
        (
            user_id,
            group_id,
        ),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def db_get_memory_by_id(user_id, group_id, user_video_id):
    """
    Retrieve a specific video from the memory table by its user_video_id.

    Args:
        user_id (int): The ID of the user.
        group_id (int): The ID of the group.
        user_video_id (int): The user-specific video ID.

    Returns:
        tuple: A tuple containing video URL, timestamp, task ID, and status.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT video_url, timestamp, task_id, status FROM memory WHERE user_id = ? AND group_id = ? AND user_video_id = ?",
        (user_id, group_id, user_video_id),
    )
    memory = c.fetchone()
    conn.close()
    return memory


def db_add_group(group_id, group_name):
    """
    Add a group to the database or update its name if it already exists.

    Args:
        group_id (int): The ID of the group.
        group_name (str): The name of the group.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO groups (group_id, group_name)
        VALUES (?, ?)
        ON CONFLICT(group_id) DO UPDATE SET group_name = excluded.group_name
        """,
        (group_id, group_name),
    )
    conn.commit()
    conn.close()


def db_get_all_groups():
    """
    Retrieve all groups from the database.

    Returns:
        list: A list of tuples containing group IDs and names.
    """
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM groups")
    groups = c.fetchall()
    conn.close()
    return groups
