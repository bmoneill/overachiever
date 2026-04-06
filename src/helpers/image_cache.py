"""
Image cache helper module.
"""
import os, requests
from flask import request
from PIL import Image

IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "img")

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
        with Image.open(target_path) as img:
            rgb_img = img.convert("RGB")
            resized_img = rgb_img.resize((128, 128))
            resized_img.save(target_path, "JPEG", optimize=True, quality=70)


    return f"{base}/{url_hash}"
