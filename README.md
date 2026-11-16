# Sitemap Extractor

貼上 sitemap 網址或網域，自動展開所有子 sitemap，把文章網址抓出來存成 CSV。

Paste a sitemap URL or a domain; child sitemaps are expanded automatically and the article URLs are exported as CSV. [English below](#english).

## 功能

- 支援一般 XML sitemap、sitemap index（多層）、gzip 壓縮檔、純文字 sitemap
- 只貼網域也可以，會自動從 `robots.txt` 和常見路徑找 sitemap
- 自動分辨頁面類型：文章、一般頁面、商品、分類與標籤、未分類
- 簡單模式只抓文章；進階設定可選類型、加關鍵字與日期條件、勾選子 sitemap
- 輸出 CSV（Excel 可直接開）、純文字清單、一鍵複製；多個網站可合併或各一份
- 介面支援中文與英文

只讀取網站公開的 sitemap，不抓取頁面內容。

## 三種用法

### 1. 本機網頁版（Windows）

雙擊 `start.bat`。第一次會自動安裝，之後瀏覽器會打開 `http://127.0.0.1:8000/`。需要 Python 3.10 以上。

其他系統：

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m web
```

### 2. 指令版

```bash
python cli.py https://example.com/sitemap.xml
python cli.py example.com another-site.com --all -o urls.csv
python cli.py urls.txt --include /blog/ --from 2026-01-01 --format txt
```

`python cli.py --help` 可看全部選項。

### 3. 公開的線上版（Docker）

```bash
docker compose up -d --build
```

服務會開在 `127.0.0.1:8000`，前面請放一層有 HTTPS 的反向代理。`docker-compose.yml` 已開啟 `PUBLIC_MODE`。

## 設定（環境變數）

| 變數 | 本機預設 | `PUBLIC_MODE=1` 預設 | 說明 |
| --- | --- | --- | --- |
| `PUBLIC_MODE` | 關 | 開 | 開啟後拒絕內部位址、只允許 80/443 埠，並套用以下限制 |
| `TRUST_PROXY` | 關 | 關 | 從 `X-Forwarded-For` 讀取訪客 IP。只有在反向代理後面才開 |
| `RATE_LIMIT_PER_HOUR` | 不限 | 20 | 每個 IP 每小時可執行的次數 |
| `MAX_INPUTS` | 200 | 10 | 一次可貼的 sitemap 數量 |
| `MAX_URLS` | 5,000,000 | 200,000 | 一次最多輸出的網址數 |
| `MAX_SECONDS` | 不限 | 300 | 單次執行時間上限 |
| `MAX_FILE_MB` | 50 | 50 | 單一 sitemap 解壓後的大小上限 |
| `MAX_CONCURRENT_JOBS` | 3 | 3 | 同時執行的工作數，其餘排隊 |
| `RESULT_TTL` | 3600 | 3600 | 結果保留秒數，之後自動刪除 |
| `HOST` / `PORT` | 127.0.0.1 / 8000 | | 監聽位址 |

## 開發

```bash
pip install -r requirements-dev.txt
pytest
```

測試全部使用內建的假資料，不會連到外部網站。

## 授權

程式碼採用 [MIT](LICENSE) 授權。

「Raze AEO」名稱與 Logo（`web/static/logo.svg`、`logo-dark.svg`、`favicon.svg`）不在 MIT 授權範圍內，版權所有。自行架設或再散布時，請換成你自己的名稱與圖示。詳見 [NOTICE](NOTICE)。

---

## English

### What it does

- Reads XML sitemaps, sitemap indexes (nested), gzipped sitemaps and plain-text sitemaps
- Accepts a bare domain and finds its sitemap through `robots.txt` and the usual paths
- Labels each URL as article, page, product, category/tag or unclassified
- Simple mode returns articles only; advanced settings add type, keyword, date and per-sitemap filters
- Exports CSV (opens in Excel), plain text, or copies to the clipboard
- Interface in Chinese and English

Only public sitemaps are read; page content is never fetched.

### Run it

- **Local web UI:** double-click `start.bat` on Windows, or `python -m web` after `pip install -r requirements.txt`.
- **Command line:** `python cli.py https://example.com/sitemap.xml --lang en` (`--help` lists every option).
- **Public deployment:** `docker compose up -d --build`, then put an HTTPS reverse proxy in front of `127.0.0.1:8000`.

`PUBLIC_MODE=1` blocks internal addresses and non-standard ports and applies rate, size and time limits. See the table above for every setting.

### License

The code is released under the [MIT License](LICENSE). The "Raze AEO" name and logo (`web/static/logo.svg`, `logo-dark.svg`, `favicon.svg`) are not covered by it; all rights reserved. Replace them with your own if you host or redistribute this tool. See [NOTICE](NOTICE).
