"""
Image cache helper module.
"""
import os, urllib.request
from urllib.parse import urlparse
from flask import request

IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "img")

def get_image_path(image_url: str) -> str:
    """
    Caches an image from the given URL if it does not exist and returns the path to the cached image.
    """

    base = f"{request.host_url}/static/img"

    if not os.path.exists(IMAGE_CACHE_DIR):
        os.makedirs(IMAGE_CACHE_DIR)

    url_hash = hash(image_url)

    if not os.path.exists(os.path.join(IMAGE_CACHE_DIR, f"{url_hash}")):
        with open(f"{IMAGE_CACHE_DIR}/{url_hash}", "wb") as f:
            f.write(urllib.request.urlopen(image_url).read())

    return f"{base}/{url_hash}"
