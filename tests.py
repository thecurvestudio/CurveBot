import os
import sqlite3
import pytest
from unittest.mock import AsyncMock, patch
import logging
from datetime import datetime
from services import (
    init_db,
    db_get_month,
    db_get_reference,
    db_add_reference,
    db_update_usage,
    db_get_limits,
    db_set_group_limit,
    db_set_user_limit,
    db_get_usage,
    db_add_memory,
    db_get_memory,
    db_update_video_url,
    db_update_status,
    get_db_path,
)
from bot import imagine

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Override environment variable for the database path
    TEST_DB = os.environ["DATABASE"]
    # Drop old test database if exists
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Create schema
    init_db()

    yield  # Run the tests

    # Cleanup after tests
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_db_get_month():
    assert db_get_month() == datetime.utcnow().strftime("%Y-%m")


def test_db_add_and_get_reference():
    group_id = 1
    ref = "Test Reference"
    db_add_reference(group_id, ref)
    assert db_get_reference(group_id) == ref


def test_db_update_usage():
    group_id = 2
    user_id = 3

    db_update_usage(group_id, user_id)
    db_update_usage(group_id, user_id)

    group_calls, user_calls = db_get_usage(group_id, user_id)
    assert group_calls == 2
    assert user_calls == 2


def test_db_get_limits():
    group_id = 1
    db_set_group_limit(group_id, 100)
    db_set_user_limit(group_id, 10)
    group_limit, user_limit = db_get_limits(group_id)
    assert group_limit == 100
    assert user_limit == 10


def test_db_set_group_limit():
    group_id = 4
    group_limit = 50
    db_set_group_limit(group_id, group_limit)
    assert db_get_limits(group_id)[0] == group_limit


def test_db_set_user_limit():
    group_id = 5
    user_limit = 5
    db_set_user_limit(group_id, user_limit)
    assert db_get_limits(group_id)[1] == user_limit


def test_db_get_usage():
    group_id = 6
    user_id = 7
    db_update_usage(group_id, user_id)
    assert db_get_usage(group_id, user_id) == (1, 1)

    db_update_usage(group_id, user_id)
    assert db_get_usage(group_id, user_id) == (2, 2)


def test_db_add_and_get_memory():
    user_id = 9
    video_url = "http://example.com/video.mp4"
    task_id = "task_001"
    status = "pending"

    # Add memory entry
    db_add_memory(user_id, video_url, task_id, status)

    # Retrieve memory entries
    memory = db_get_memory(user_id)

    # Assertions
    assert len(memory) == 1
    assert memory[0][0] == video_url  # Check video URL
    assert isinstance(memory[0][1], str)  # Check timestamp is a string

    # Update video URL
    new_video_url = "http://example.com/new_video.mp4"
    db_update_video_url(user_id, task_id, new_video_url)

    # Retrieve updated memory
    memory = db_get_memory(user_id)
    assert memory[0][0] == new_video_url  # Check updated video URL

    # Update status
    new_status = "completed"
    db_update_status(user_id, task_id, new_status)

    # Verify status update (requires a separate query if needed)
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT status FROM memory WHERE user_id = ? AND task_id = ?",
        (user_id, task_id),
    )
    updated_status = c.fetchone()[0]
    conn.close()
    assert updated_status == new_status  # Check updated status


@pytest.mark.asyncio
async def test_imagine_successful_generation():
    # Mock the update and context
    mock_update = AsyncMock()
    mock_context = AsyncMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 67890
    mock_context.args = ["test", "prompt"]

    # Mock database and API calls
    with patch("bot.API_KEY", "abc"), patch(
        "bot.db_get_limits", return_value=(10, 5)
    ) as mock_get_limits, patch(
        "bot.db_get_usage", return_value=(2, 1)
    ) as mock_get_usage, patch(
        "bot.db_get_reference", return_value="http://example.com/image.jpg"
    ) as mock_get_reference, patch(
        "bot.reference_to_video",
        return_value={"task_id": "task_001", "state": "created"},
    ) as mock_reference_to_video, patch(
        "bot.get_generation_status",
        side_effect=[
            {"state": "success", "creations": [{"url": "http://example.com/video.mp4"}]}
        ],
    ) as mock_get_generation_status, patch(
        "bot.db_add_memory"
    ) as mock_add_memory, patch(
        "bot.db_update_usage"
    ) as mock_update_usage, patch(
        "bot.db_update_video_url"
    ) as mock_update_video_url:

        # Call the imagine function
        await imagine(mock_update, mock_context)

        # Assertions
        mock_get_limits.assert_called_once_with(12345)
        mock_get_usage.assert_called_once_with(12345, 67890)
        mock_get_reference.assert_called_once_with(12345)
        mock_reference_to_video.assert_called_once_with(
            mock=False,
            api_key="abc",
            model="vidu1.5",
            images=["http://example.com/image.jpg"],
            prompt="test prompt, 2d animation",
            duration=4,
            aspect_ratio="16:9",
            resolution="360p",
        )
        mock_add_memory.assert_called_once_with(
            user_id=67890, video_url="", task_id="task_001", status="pending"
        )
        mock_get_generation_status.assert_called()
        mock_update_usage.assert_called_once_with(12345, 67890)
        mock_update_video_url.assert_called_once_with(
            67890, "task_001", "http://example.com/video.mp4"
        )
        mock_update.message.reply_video.assert_called_once_with(
            video="http://example.com/video.mp4"
        )


@pytest.mark.asyncio
async def test_imagine_group_limit_reached():
    # Mock the update and context
    mock_update = AsyncMock()
    mock_context = AsyncMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 67890
    mock_context.args = ["test", "prompt"]

    # Mock database and API calls
    with patch("bot.API_KEY", "abc"), patch(
        "bot.db_get_limits", return_value=(10, 5)
    ) as mock_get_limits, patch(
        "bot.db_get_usage", return_value=(11, 1)
    ) as mock_get_usage, patch(
        "bot.db_get_reference", return_value="http://example.com/image.jpg"
    ) as mock_get_reference, patch(
        "bot.reference_to_video",
        return_value={"task_id": "task_001", "state": "created"},
    ) as mock_reference_to_video:

        # Call the imagine function
        await imagine(mock_update, mock_context)

        # Assertions
        mock_get_limits.assert_called_once_with(12345)
        mock_get_usage.assert_called_once_with(12345, 67890)
        mock_get_reference.assert_not_called()
        mock_reference_to_video.assert_not_called()

        # Check the message sent to the user
        mock_update.message.reply_text.assert_called_once_with(
            "Group has reached its monthly limit."
        )


@pytest.mark.asyncio
async def test_imagine_user_limit_reached():
    # Mock the update and context
    mock_update = AsyncMock()
    mock_context = AsyncMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_user.id = 67890
    mock_context.args = ["test", "prompt"]

    # Mock database and API calls
    with patch("bot.API_KEY", "abc"), patch(
        "bot.db_get_limits", return_value=(10, 5)
    ) as mock_get_limits, patch(
        "bot.db_get_usage", return_value=(1, 6)
    ) as mock_get_usage, patch(
        "bot.db_get_reference", return_value="http://example.com/image.jpg"
    ) as mock_get_reference, patch(
        "bot.reference_to_video",
        return_value={"task_id": "task_001", "state": "created"},
    ) as mock_reference_to_video:

        # Call the imagine function
        await imagine(mock_update, mock_context)

        # Assertions
        mock_get_limits.assert_called_once_with(12345)
        mock_get_usage.assert_called_once_with(12345, 67890)
        mock_get_reference.assert_not_called()
        mock_reference_to_video.assert_not_called()

        # Check the message sent to the user
        mock_update.message.reply_text.assert_called_once_with(
            "You have reached your monthly limit."
        )
