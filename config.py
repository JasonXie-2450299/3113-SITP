"""Shared API endpoints, headers, and Bilibili signing constants."""

API_ROOT = "https://api.bilibili.com"
SEARCH_URL = f"{API_ROOT}/x/web-interface/search/type"
SEARCH_WBI_URL = f"{API_ROOT}/x/web-interface/wbi/search/type"
COMMENT_URL = f"{API_ROOT}/x/v2/reply/main"
COMMENT_WBI_URL = f"{API_ROOT}/x/v2/reply/wbi/main"
PAGELIST_URL = f"{API_ROOT}/x/player/pagelist"
DANMAKU_URL = f"{API_ROOT}/x/v1/dm/list.so"
DANMAKU_VIEW_URL = f"{API_ROOT}/x/v2/dm/web/view"
DANMAKU_SEG_URL = f"{API_ROOT}/x/v2/dm/web/seg.so"
NAV_URL = f"{API_ROOT}/x/web-interface/nav"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Current WBI mixin-key index table used by Bilibili's signed endpoints.
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 36, 25, 1, 4, 40, 44, 51, 6, 16, 21, 20, 30, 34, 22, 11,
    17, 52, 26, 0, 24, 57, 7, 48, 54, 55, 56, 61, 60, 59, 64, 62,
]

RISK_CODES = {-352, -412, -403, 403, 412}
