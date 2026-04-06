import requests
import time

API_CACHE_EXPIRY = 60 * 60 # 1 hour
API_CACHE = {}
TIMEOUT = 15

def _build_cache_key(url: str, params: dict | None = None) -> str:
    return f"{url}{params}"

def make_request(url: str, method: str = "GET", headers: dict | None = None, params: dict | None = None) -> requests.Response:
    cache_key = _build_cache_key(url, params)
    if cache_key in API_CACHE:
        if time.time() - API_CACHE[cache_key]["time"] > API_CACHE_EXPIRY:
            del API_CACHE[cache_key]
        else:
            return API_CACHE[cache_key]["response"]
    response = requests.request(method, url, headers=headers, params=params, timeout=TIMEOUT)
    if response.status_code != 200:
        return response

    API_CACHE[cache_key] = {
        "response": response,
        "time": time.time(),
    }

    return response
