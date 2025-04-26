import requests


def reference_to_video(
    api_key,
    model,
    images,
    prompt,
    duration=4,
    seed=None,
    aspect_ratio="16:9",
    resolution="360p",
    movement_amplitude="auto",
    callback_url=None,
):
    """
    Make a POST request to the Vidu API to generate a video from a reference.

    Args:
        api_key (str): Your API key for authorization.
        model (str): The model name. Accepted values: "vidu2.0", "vidu1.5", "vidu1.0".
        images (list): List of image URLs or Base64-encoded strings.
        prompt (str): Text prompt for video generation (max 1500 characters).
        duration (int, optional): Duration of the video. Defaults to 4.
        seed (int, optional): Random seed for video generation.
        aspect_ratio (str, optional): Aspect ratio of the video. Defaults to "16:9".
        resolution (str, optional): Resolution of the video. Defaults to "360p".
        movement_amplitude (str, optional): Movement amplitude. Defaults to "auto".
        callback_url (str, optional): Callback URL for task status updates.

    Returns:
        dict: The response from the API.
    """
    print(f"Calling reference_to_video with: {api_key}")
    url = "https://api.vidu.com/ent/v2/reference2video"
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "images": images,
        "prompt": prompt,
        "duration": duration,
        "seed": seed,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "movement_amplitude": movement_amplitude,
        "callback_url": callback_url,
    }

    # Remove keys with None values
    payload = {key: value for key, value in payload.items() if value is not None}

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()


def get_generation_status(api_key, task_id):
    """
    Get the status and results of a video generation task from the Vidu API.

    Args:
        api_key (str): Your API key for authorization.
        task_id (str): The task ID returned upon the successful creation of a task.

    Returns:
        dict: The response from the API containing the task status and generated results.
    """
    print(f"Calling get_generation_status with: {api_key}")
    url = f"https://api.vidu.com/ent/v2/tasks/{task_id}/creations"
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()
