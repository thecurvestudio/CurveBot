import os
import pytest
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
)

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


def test_db_add_and_get_memory():
    user_id = 9
    video_url = "http://example.com/video.mp4"
    db_add_memory(user_id, video_url)
    memory = db_get_memory(user_id)
    assert len(memory) == 1
    assert memory[0][0] == video_url
