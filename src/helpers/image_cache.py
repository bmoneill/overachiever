"""
Image cache helper module.
"""

import os
import threading

import requests
from flask import request
from PIL import Image

IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "img")


def _compress_image(image_path: str) -> None:
    with Image.open(image_path) as img:
        rgb_img = img.convert("RGB")
        ratio = img.width / img.height
        resized_img = rgb_img.resize((int(128 * ratio), 128))
        resized_img.save(image_path, "JPEG", optimize=True, quality=70)


def get_image_path(image_url: str) -> str:
    """
    Caches an image from the given URL if it does not exist and returns the path to the cached image.
    """

    base = f"{request.host_url}/static/img"

    if not os.path.exists(IMAGE_CACHE_DIR):
        os.makedirs(IMAGE_CACHE_DIR)

    url_hash = hash(image_url)
    target_path = f"{IMAGE_CACHE_DIR}/{url_hash}"

    if not os.path.exists(target_path):
        with open(target_path, "wb") as f:
            response = requests.get(image_url, stream=True)
            for block in response.iter_content(1024):
                if not block:
                    break
                f.write(block)

        t = threading.Thread(target=_compress_image, args=(target_path))
        t.start()

    return f"{base}/{url_hash}"
