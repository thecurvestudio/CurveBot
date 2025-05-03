import re
import logging


def validate_and_extract_urls(file_path):
    """
    Reads a .txt file and validates that it contains a list of URLs.

    Args:
        file_path (str): The path to the .txt file.

    Returns:
        list: A list of valid URLs if the file is valid.
        None: If the file contains invalid data.
    """
    url_pattern = re.compile(r"^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(/.*)?$")
    valid_urls = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            url = line.strip()
            if url_pattern.match(url):
                valid_urls.append(url)
            else:
                # If any line is not a valid URL, return None
                return None

        return valid_urls if valid_urls else None
    except Exception as e:
        logging.error(f"Error reading or validating file: {e}")
        return None
