"""Human-readable text for error codes, in Chinese and English."""
from __future__ import annotations

ERROR_MESSAGES = {
    "zh": {
        "blocked": "網站拒絕了請求（可能有機器人防護）",
        "not_found": "找不到這個檔案（404）",
        "timeout": "連線逾時",
        "network": "連線失敗",
        "too_large": "檔案超過大小上限",
        "bad_gzip": "壓縮檔損毀",
        "unsafe_url": "這個網址不允許抓取",
        "too_many_redirects": "轉址次數過多",
        "deadline": "已達時間上限",
        "http_error": "伺服器回應錯誤",
        "not_sitemap": "這不是 sitemap",
        "no_sitemap": "找不到這個網站的 sitemap",
        "too_deep": "sitemap index 層數過多",
        "bad_input": "網址格式不正確",
        "too_many_inputs": "輸入的網址數量超過上限",
    },
    "en": {
        "blocked": "The site refused the request (bot protection?)",
        "not_found": "File not found (404)",
        "timeout": "The request timed out",
        "network": "Connection failed",
        "too_large": "The file exceeds the size limit",
        "bad_gzip": "The gzip file is corrupt",
        "unsafe_url": "This URL is not allowed",
        "too_many_redirects": "Too many redirects",
        "deadline": "Time limit reached",
        "http_error": "The server returned an error",
        "not_sitemap": "This is not a sitemap",
        "no_sitemap": "No sitemap found for this site",
        "too_deep": "Sitemap index nesting is too deep",
        "bad_input": "Not a valid URL",
        "too_many_inputs": "Too many inputs",
    },
}

TRUNCATED_MESSAGES = {
    "zh": {
        "max_urls": "已達網址數量上限，結果不完整",
        "deadline": "已達時間上限，結果不完整",
        "max_sitemaps": "子 sitemap 數量過多，結果不完整",
        "cancelled": "已取消",
    },
    "en": {
        "max_urls": "URL limit reached; results are incomplete",
        "deadline": "Time limit reached; results are incomplete",
        "max_sitemaps": "Too many child sitemaps; results are incomplete",
        "cancelled": "Cancelled",
    },
}


def error_text(code: str, lang: str = "zh") -> str:
    table = ERROR_MESSAGES.get(lang, ERROR_MESSAGES["en"])
    if code in table:
        return table[code]
    if code.startswith("http_"):
        return f"{table['http_error']} ({code[5:]})"
    return code
