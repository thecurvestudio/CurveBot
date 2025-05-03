from services import db_add_memory, db_update_video_url, db_update_status, init_db

init_db()
# db_add_memory(user_id=123, video_url="", task_id="task_001")
# db_update_video_url(user_id=123, task_id="task_001", video_url="http://example.com/new_video.mp4")
db_update_status(user_id=123, task_id="task_001", status="completed")
