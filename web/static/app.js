(function () {
  'use strict';

  var TYPES = ['article', 'page', 'product', 'taxonomy', 'other'];

  var I18N = {
    zh: {
      title: '從 Sitemap 抓出文章網址',
      lead: '貼上 sitemap 網址或網域，自動展開所有子 sitemap，下載成 CSV。',
      inputLabel: 'Sitemap 網址',
      inputHint: '一行一個，可以貼多個。只貼網域也可以，工具會自己找 sitemap。',
      inputHintLimit: '一行一個，一次最多 {n} 個。只貼網域也可以，工具會自己找 sitemap。',
      advanced: '進階設定',
      typesLegend: '要包含的頁面類型',
      includeLabel: '網址必須包含',
      excludeLabel: '網址必須排除',
      keywordHint: '多個關鍵字用逗號分隔。「必須包含」符合任一個即可。',
      dateFrom: '更新日期：從',
      dateTo: '到',
      dateHint: '設定日期後，sitemap 裡沒有標示更新日期的網址會被排除。',
      outputLegend: '多個網站時的輸出方式',
      merged: '合併成一份 CSV',
      split: '每個網站各一份（ZIP）',
      sourcesLegend: '子 sitemap（取消勾選即不納入）',
      selectAll: '全選',
      selectNone: '全不選',
      submit: '抓取文章網址',
      cancel: '取消',
      working: '抓取中…',
      queued: '排隊中，請稍候…',
      progress: '已抓 {done} / {total} 個 sitemap，找到 {urls} 個網址',
      resultCount: '共找到 {n} 個網址',
      resultNone: '沒有符合條件的網址',
      fallbackNotice: '{sites} 無法自動分辨哪些是文章，已列出全部網址。可以在進階設定用關鍵字篩選。',
      downloadCsv: '下載 CSV',
      downloadZip: '下載 ZIP',
      copyAll: '複製全部網址',
      downloadTxt: '下載 TXT',
      copied: '已複製',
      previewNote: '預覽前 {n} 筆，下載的檔案包含全部。',
      colUrl: '網址',
      colLastmod: '最後更新',
      colType: '類型',
      errorsSummary: '{n} 個 sitemap 抓取失敗',
      footer: '只讀取網站公開的 sitemap，不抓取文章內容。結果暫存 1 小時後自動刪除。',
      source: '開放原始碼（MIT）',
      types: { article: '文章', page: '一般頁面', product: '商品', taxonomy: '分類與標籤', other: '未分類' },
      truncated: {
        max_urls: '已達網址數量上限，結果不完整。',
        deadline: '已達時間上限，結果不完整。',
        max_sitemaps: '子 sitemap 數量過多，結果不完整。',
        cancelled: '已取消，以下是取消前抓到的結果。'
      },
      errors: {
        blocked: '網站拒絕了請求（可能有機器人防護）',
        not_found: '找不到這個檔案（404）',
        timeout: '連線逾時',
        network: '連線失敗',
        too_large: '檔案超過大小上限',
        bad_gzip: '壓縮檔損毀',
        unsafe_url: '這個網址不允許抓取',
        too_many_redirects: '轉址次數過多',
        deadline: '已達時間上限',
        http_error: '伺服器回應錯誤',
        not_sitemap: '這不是 sitemap',
        no_sitemap: '找不到這個網站的 sitemap',
        too_deep: 'sitemap index 層數過多',
        bad_input: '網址格式不正確',
        too_many_inputs: '輸入的網址數量超過上限',
        internal: '程式發生錯誤',
        rate_limited: '使用次數已達上限，請一小時後再試。',
        busy: '目前使用人數較多，請稍後再試。',
        job_not_found: '結果已過期，請重新抓取。',
        bad_request: '輸入內容有誤，請檢查後再試。',
        empty: '請先貼上至少一個 sitemap 網址。',
        unknown: '發生錯誤，請稍後再試。'
      }
    },
    en: {
      title: 'Extract article URLs from a sitemap',
      lead: 'Paste a sitemap URL or a domain. Child sitemaps are expanded automatically; download the result as CSV.',
      inputLabel: 'Sitemap URL',
      inputHint: 'One per line; several are fine. A bare domain works too: the tool looks for its sitemap.',
      inputHintLimit: 'One per line, up to {n} at a time. A bare domain works too: the tool looks for its sitemap.',
      advanced: 'Advanced settings',
      typesLegend: 'Page types to include',
      includeLabel: 'URL must contain',
      excludeLabel: 'URL must not contain',
      keywordHint: 'Separate keywords with commas. "Must contain" matches any one of them.',
      dateFrom: 'Last modified: from',
      dateTo: 'to',
      dateHint: 'With a date set, URLs that have no last-modified date in the sitemap are left out.',
      outputLegend: 'Output for several sites',
      merged: 'One merged CSV',
      split: 'One CSV per site (ZIP)',
      sourcesLegend: 'Child sitemaps (untick to leave one out)',
      selectAll: 'Select all',
      selectNone: 'Select none',
      submit: 'Extract article URLs',
      cancel: 'Cancel',
      working: 'Working…',
      queued: 'Queued, please wait…',
      progress: 'Fetched {done} of {total} sitemaps, {urls} URLs found',
      resultCount: '{n} URLs found',
      resultNone: 'No matching URLs',
      fallbackNotice: 'Could not tell which pages are articles on {sites}, so every URL is listed. Use the keyword filters in Advanced settings to narrow it down.',
      downloadCsv: 'Download CSV',
      downloadZip: 'Download ZIP',
      copyAll: 'Copy all URLs',
      downloadTxt: 'Download TXT',
      copied: 'Copied',
      previewNote: 'Showing the first {n}. The download contains all of them.',
      colUrl: 'URL',
      colLastmod: 'Last modified',
      colType: 'Type',
      errorsSummary: '{n} sitemaps could not be fetched',
      footer: 'Reads public sitemaps only; page content is never fetched. Results are deleted after one hour.',
      source: 'Open source (MIT)',
      types: { article: 'Article', page: 'Page', product: 'Product', taxonomy: 'Category / tag', other: 'Unclassified' },
      truncated: {
        max_urls: 'URL limit reached; results are incomplete.',
        deadline: 'Time limit reached; results are incomplete.',
        max_sitemaps: 'Too many child sitemaps; results are incomplete.',
        cancelled: 'Cancelled. These are the results collected so far.'
      },
      errors: {
        blocked: 'The site refused the request (bot protection?)',
        not_found: 'File not found (404)',
        timeout: 'The request timed out',
        network: 'Connection failed',
        too_large: 'The file exceeds the size limit',
        bad_gzip: 'The gzip file is corrupt',
        unsafe_url: 'This URL is not allowed',
        too_many_redirects: 'Too many redirects',
        deadline: 'Time limit reached',
        http_error: 'The server returned an error',
        not_sitemap: 'This is not a sitemap',
        no_sitemap: 'No sitemap found for this site',
        too_deep: 'Sitemap index nesting is too deep',
        bad_input: 'Not a valid URL',
        too_many_inputs: 'Too many URLs',
        internal: 'Something went wrong',
        rate_limited: 'Usage limit reached. Please try again in an hour.',
        busy: 'The tool is busy right now. Please try again shortly.',
        job_not_found: 'These results have expired. Please run the extraction again.',
        bad_request: 'Something in the input is not valid. Please check and retry.',
        empty: 'Paste at least one sitemap URL first.',
        unknown: 'Something went wrong. Please try again.'
      }
    }
  };

  var $ = function (id) { return document.getElementById(id); };
  var state = { lang: 'zh', config: null, jobId: null, job: null, running: false, lastResult: null, timer: null };

  function storedLang() {
    try { return localStorage.getItem('lang'); } catch (e) { return null; }
  }
  function storeLang(lang) {
    try { localStorage.setItem('lang', lang); } catch (e) { /* storage unavailable */ }
  }

  function t(key, vars) {
    var text = I18N[state.lang][key] || key;
    if (vars) {
      Object.keys(vars).forEach(function (k) { text = text.replace('{' + k + '}', vars[k]); });
    }
    return text;
  }
  function errorText(code) {
    var table = I18N[state.lang].errors;
    if (table[code]) { return table[code]; }
    if (code && code.indexOf('http_') === 0) { return table.http_error + ' (' + code.slice(5) + ')'; }
    return table.unknown;
  }
  function num(n) { return Number(n).toLocaleString(state.lang === 'zh' ? 'zh-TW' : 'en-US'); }

  function applyLang() {
    document.documentElement.lang = state.lang === 'zh' ? 'zh-Hant' : 'en';
    document.title = 'Sitemap Extractor - ' + t('title');
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n]'), function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    $('lang-toggle').textContent = state.lang === 'zh' ? 'English' : '中文';
    var limit = state.config && state.config.public_mode ? state.config.max_inputs : 0;
    $('input-hint').textContent = limit ? t('inputHintLimit', { n: limit }) : t('inputHint');
    renderTypeChecks();
    if (state.running) { $('submit').textContent = t('working'); }
    if (state.job) { renderProgress(state.job); renderSources(); renderErrors(); }
    if (state.lastResult) { renderResult(state.lastResult); }
    updateDownloadLabel();
  }

  function typeTotals() {
    var totals = {};
    if (state.job && state.job.type_counts) {
      Object.keys(state.job.type_counts).forEach(function (site) {
        var counts = state.job.type_counts[site];
        Object.keys(counts).forEach(function (k) { totals[k] = (totals[k] || 0) + counts[k]; });
      });
    }
    return totals;
  }

  function renderTypeChecks() {
    var box = $('type-checks');
    var checked = {};
    var existing = box.querySelectorAll('input');
    if (existing.length) {
      Array.prototype.forEach.call(existing, function (el) { checked[el.value] = el.checked; });
    } else {
      checked.article = true;
    }
    var totals = typeTotals();
    var known = state.job && state.job.type_counts;
    box.textContent = '';
    TYPES.forEach(function (type) {
      var label = document.createElement('label');
      var input = document.createElement('input');
      input.type = 'checkbox';
      input.value = type;
      input.checked = !!checked[type];
      input.addEventListener('change', scheduleRefresh);
      label.appendChild(input);
      label.appendChild(document.createTextNode(' ' + I18N[state.lang].types[type]));
      if (known) {
        var count = document.createElement('span');
        count.className = 'count';
        count.textContent = '(' + num(totals[type] || 0) + ')';
        label.appendChild(count);
      }
      box.appendChild(label);
    });
  }

  function splitKeywords(value) {
    return value.split(/[,，\n]+/).map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 20);
  }

  function currentFilter() {
    var types = [];
    Array.prototype.forEach.call($('type-checks').querySelectorAll('input'), function (el) {
      if (el.checked) { types.push(el.value); }
    });
    var skip = [];
    Array.prototype.forEach.call($('sources').querySelectorAll('input'), function (el) {
      if (!el.checked) { skip.push(Number(el.value)); }
    });
    return {
      types: types.length === TYPES.length ? null : types,
      include: splitKeywords($('include').value),
      exclude: splitKeywords($('exclude').value),
      date_from: $('date-from').value || '',
      date_to: $('date-to').value || '',
      skip_sources: skip,
      fallback: true
    };
  }

  function showMessage(code) {
    var el = $('message');
    if (!code) { el.hidden = true; return; }
    el.textContent = errorText(code);
    el.hidden = false;
  }

  function api(method, path, body) {
    var options = { method: method, headers: {} };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    return fetch(path, options).then(function (resp) {
      if (resp.ok) { return resp; }
      return resp.json().catch(function () { return {}; }).then(function (data) {
        var err = new Error(typeof data.error === 'string' ? data.error : 'unknown');
        err.code = typeof data.error === 'string' ? data.error : (resp.status === 422 ? 'bad_request' : 'unknown');
        throw err;
      });
    });
  }

  function setRunning(running) {
    state.running = running;
    $('submit').disabled = running;
    $('submit').textContent = running ? t('working') : t('submit');
    $('cancel').hidden = !running;
  }

  function renderProgress(job) {
    var text = job.status === 'queued' ? t('queued') : t('progress', {
      done: num(job.sitemaps_done), total: num(job.sitemaps_total), urls: num(job.urls)
    });
    $('progress-text').textContent = text;
    var bar = $('progress-bar');
    if (job.status === 'done') {
      bar.max = 1; bar.value = 1;
    } else if (job.sitemaps_total > 0) {
      bar.max = job.sitemaps_total; bar.value = job.sitemaps_done;
    } else {
      bar.removeAttribute('value');
    }
  }

  function renderSources() {
    var box = $('sources');
    var sources = (state.job && state.job.sources) || [];
    var unchecked = {};
    Array.prototype.forEach.call(box.querySelectorAll('input'), function (el) {
      if (!el.checked) { unchecked[el.value] = true; }
    });
    box.textContent = '';
    $('sources-box').hidden = sources.length < 2;
    sources.forEach(function (src) {
      var label = document.createElement('label');
      var input = document.createElement('input');
      input.type = 'checkbox';
      input.value = String(src.index);
      input.checked = !unchecked[String(src.index)];
      input.addEventListener('change', scheduleRefresh);
      var url = document.createElement('span');
      url.className = 'src-url';
      url.textContent = src.url;
      var count = document.createElement('span');
      count.className = 'count';
      var typeText = src.type ? I18N[state.lang].types[src.type] + ' · ' : '';
      count.textContent = typeText + num(src.count);
      label.appendChild(input);
      label.appendChild(url);
      label.appendChild(count);
      box.appendChild(label);
    });
  }

  function renderErrors() {
    var errors = (state.job && state.job.errors) || [];
    $('errors-box').hidden = errors.length === 0;
    $('errors-summary').textContent = t('errorsSummary', { n: num(errors.length) });
    var list = $('errors');
    list.textContent = '';
    errors.forEach(function (err) {
      var li = document.createElement('li');
      li.textContent = (err.url ? err.url + ' — ' : '') + errorText(err.code);
      list.appendChild(li);
    });
    var truncated = state.job && state.job.truncated;
    $('truncated').hidden = !truncated;
    if (truncated) { $('truncated').textContent = I18N[state.lang].truncated[truncated] || truncated; }
  }

  function safeHref(url) {
    return /^https?:\/\//i.test(url) ? url : null;
  }

  function renderResult(result) {
    state.lastResult = result;
    $('result-box').hidden = false;
    $('result-count').textContent = result.total ? t('resultCount', { n: num(result.total) }) : t('resultNone');
    var notice = $('result-notice');
    notice.hidden = !(result.fallback_sites && result.fallback_sites.length && result.total);
    if (!notice.hidden) { notice.textContent = t('fallbackNotice', { sites: result.fallback_sites.join(', ') }); }
    var hasRows = result.total > 0;
    $('download-csv').disabled = !hasRows;
    $('copy-all').disabled = !hasRows;
    $('download-txt').disabled = !hasRows;
    $('preview-note').textContent = result.total > result.rows.length
      ? t('previewNote', { n: num(result.rows.length) }) : '';
    var body = $('rows');
    body.textContent = '';
    result.rows.forEach(function (row) {
      var tr = document.createElement('tr');
      var urlCell = document.createElement('td');
      urlCell.className = 'url';
      var href = safeHref(row[1]);
      if (href) {
        var a = document.createElement('a');
        a.href = href;
        a.target = '_blank';
        a.rel = 'noopener noreferrer nofollow';
        a.textContent = row[1];
        urlCell.appendChild(a);
      } else {
        urlCell.textContent = row[1];
      }
      var modCell = document.createElement('td');
      modCell.className = 'nowrap';
      modCell.textContent = (row[2] || '').slice(0, 10);
      var typeCell = document.createElement('td');
      typeCell.className = 'nowrap';
      typeCell.textContent = I18N[state.lang].types[row[4]] || row[4];
      tr.appendChild(urlCell);
      tr.appendChild(modCell);
      tr.appendChild(typeCell);
      body.appendChild(tr);
    });
    updateDownloadLabel();
  }

  function wantsZip() {
    var split = document.querySelector('input[name="split"]:checked');
    var sites = state.lastResult ? state.lastResult.sites.length : 0;
    return !!split && split.value === 'split' && sites > 1;
  }
  function updateDownloadLabel() {
    $('download-csv').textContent = wantsZip() ? t('downloadZip') : t('downloadCsv');
  }

  function refreshResults() {
    if (!state.jobId || !state.job || state.job.status !== 'done') { return; }
    var jobId = state.jobId;
    api('POST', '/api/jobs/' + jobId + '/results', currentFilter())
      .then(function (resp) { return resp.json(); })
      .then(function (result) { if (jobId === state.jobId) { showMessage(null); renderResult(result); } })
      .catch(function (err) { showMessage(err.code || 'unknown'); });
  }
  function scheduleRefresh() {
    clearTimeout(state.timer);
    state.timer = setTimeout(refreshResults, 300);
  }

  function poll() {
    var jobId = state.jobId;
    api('GET', '/api/jobs/' + jobId)
      .then(function (resp) { return resp.json(); })
      .then(function (job) {
        if (jobId !== state.jobId) { return; }
        state.job = job;
        renderProgress(job);
        if (job.status === 'done') {
          setRunning(false);
          renderTypeChecks();
          renderSources();
          renderErrors();
          refreshResults();
        } else {
          setTimeout(poll, 1000);
        }
      })
      .catch(function (err) {
        if (jobId !== state.jobId) { return; }
        setRunning(false);
        showMessage(err.code || 'unknown');
      });
  }

  function start(event) {
    event.preventDefault();
    if (state.running) { return; }
    var inputs = $('inputs').value.split(/[\s,]+/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (!inputs.length) { showMessage('empty'); return; }
    showMessage(null);
    state.jobId = null;
    state.job = null;
    state.lastResult = null;
    $('sources').textContent = '';
    $('sources-box').hidden = true;
    $('result-box').hidden = true;
    $('progress-box').hidden = false;
    $('progress-text').textContent = t('working');
    $('progress-bar').removeAttribute('value');
    setRunning(true);
    api('POST', '/api/jobs', { inputs: inputs })
      .then(function (resp) { return resp.json(); })
      .then(function (data) { state.jobId = data.id; poll(); })
      .catch(function (err) {
        setRunning(false);
        $('progress-box').hidden = true;
        showMessage(err.code || 'unknown');
      });
  }

  function cancel() {
    if (state.jobId) { api('DELETE', '/api/jobs/' + state.jobId).catch(function () {}); }
  }

  function download(format) {
    if (!state.jobId) { return Promise.resolve(null); }
    var body = currentFilter();
    body.format = format;
    body.lang = state.lang;
    return api('POST', '/api/jobs/' + state.jobId + '/download', body).catch(function (err) {
      showMessage(err.code || 'unknown');
      return null;
    });
  }

  function saveResponse(resp) {
    if (!resp) { return; }
    var disposition = resp.headers.get('Content-Disposition') || '';
    var match = /filename="([^"]+)"/.exec(disposition);
    var name = match ? match[1] : 'sitemap-urls';
    resp.blob().then(function (blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      area.remove();
      if (ok) { resolve(); } else { reject(new Error('copy failed')); }
    });
  }

  function copyAll() {
    download('txt').then(function (resp) {
      if (!resp) { return; }
      return resp.text().then(copyText).then(function () {
        $('copied').hidden = false;
        setTimeout(function () { $('copied').hidden = true; }, 2500);
      });
    }).catch(function () { showMessage('unknown'); });
  }

  function setAllSources(checked) {
    Array.prototype.forEach.call($('sources').querySelectorAll('input'), function (el) { el.checked = checked; });
    scheduleRefresh();
  }

  function init() {
    var saved = storedLang();
    state.lang = saved === 'zh' || saved === 'en' ? saved
      : ((navigator.language || 'zh').toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en');
    applyLang();

    $('form').addEventListener('submit', start);
    $('cancel').addEventListener('click', cancel);
    $('lang-toggle').addEventListener('click', function () {
      state.lang = state.lang === 'zh' ? 'en' : 'zh';
      storeLang(state.lang);
      applyLang();
    });
    ['include', 'exclude', 'date-from', 'date-to'].forEach(function (id) {
      $(id).addEventListener('input', scheduleRefresh);
    });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="split"]'), function (el) {
      el.addEventListener('change', updateDownloadLabel);
    });
    $('sources-all').addEventListener('click', function () { setAllSources(true); });
    $('sources-none').addEventListener('click', function () { setAllSources(false); });
    $('download-csv').addEventListener('click', function () {
      download(wantsZip() ? 'zip' : 'csv').then(saveResponse);
    });
    $('download-txt').addEventListener('click', function () { download('txt').then(saveResponse); });
    $('copy-all').addEventListener('click', copyAll);

    fetch('/api/config').then(function (resp) { return resp.json(); }).then(function (config) {
      state.config = config;
      applyLang();
    }).catch(function () { /* the page still works without it */ });
  }

  init();
})();
