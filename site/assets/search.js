const QWEN_MODE = 'qwen_reference_v1';
const byId = id => document.getElementById(id);
const mode = byId('rankMode');
const lengthSelect = byId('rankLength');
const query = byId('query');
const rankInput = byId('rankInput');
const result = byId('result');
const unrankResult = byId('unrankResult');
const charCount = byId('charCount');
const counterWrap = byId('counterWrap');
const numberReceipt = byId('numberReceipt');
const addressDetails = byId('addressDetails');
const addressFormats = byId('addressFormats');
const spacePlural = new Intl.PluralRules('ru-RU');
const spaceForms = {one: 'пробел', few: 'пробела', many: 'пробелов'};
const formatCount = count => fmt(count).replaceAll('\u00a0', '\u202f');
const pageLimit = formatCount(PAGE_LEN);
const tooLong = 'Текст превышает лимит в ' + pageLimit + ' знаков.';
let model;
let revision = 0;
let originalPage = null;
let decimalAddress = null;

async function api(path, payload) {
  const options = {cache: 'no-store'};
  if (payload !== undefined) {
    options.method = 'POST';
    options.headers = {'Content-Type': 'application/json'};
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Ошибка API (HTTP ' + response.status + ').');
  return data;
}

function setPage(page) {
  query.value = page;
  // The browser converts CR and CRLF to LF in textarea.value.
  originalPage = page;
  updateQwenHint();
}

function codePointLength(text) {
  let count = 0;
  for (const _ of text) count++;
  return count;
}

function paddedPage() {
  const text = originalPage ?? query.value;
  const remaining = PAGE_LEN - codePointLength(text);
  if (remaining < 0) throw new Error(tooLong);
  if (/[\uD800-\uDFFF]/u.test(text)) throw new Error('Текст содержит недопустимый символ Unicode.');
  return text + ' '.repeat(remaining);
}

function updateQwenHint() {
  const count = codePointLength(originalPage ?? query.value);
  const remaining = PAGE_LEN - count;
  charCount.textContent = formatCount(count) + ' / ' + pageLimit;
  counterWrap.classList.toggle('over-limit', remaining < 0);
  const hint = byId('qwenHint');
  if (remaining < 0) hint.textContent = tooLong;
  else if (remaining === 0) hint.textContent = 'Страница полная.';
  else hint.textContent = 'Справа добавим ' + formatCount(remaining) + ' ' + spaceForms[spacePlural.select(remaining)] + '.';
}

function clearAddressReceipt() {
  numberReceipt.hidden = true;
  addressDetails.open = false;
  addressFormats.textContent = '';
  decimalAddress = null;
  result.textContent = '';
}

function showAddressReceipt(decimal, hexadecimal) {
  const edge = 10;
  let preview = decimal;
  if (decimal.length > 2 * edge) {
    preview = decimal.slice(0, edge) + '…' + decimal.slice(-edge) + '\nЦифр в номере — ' + formatCount(decimal.length);
  }
  result.textContent = 'Адрес найден\n' + preview;
  addressFormats.textContent = 'Десятичный номер\n' + decimal + '\n\nШестнадцатеричный номер\n' + hexadecimal;
  decimalAddress = decimal;
  numberReceipt.hidden = false;
}

function setBusy(busy) {
  for (const id of ['rankBtn', 'unrankBtn', 'pageFile', 'copyPage', 'downloadPage']) byId(id).disabled = busy;
  query.readOnly = rankInput.readOnly = busy;
}

function changeMode() {
  ++revision;
  setBusy(false);
  const qwen = mode.value === QWEN_MODE;
  for (const id of ['fileControl', 'qwenHint', 'copyPage', 'downloadPage']) byId(id).hidden = !qwen;
  counterWrap.hidden = !qwen;
  if (qwen) updateQwenHint();
  for (const id of ['lengthControl', 'scoreBtn', 'searchBtn', 'clusterHint']) byId(id).hidden = qwen;
  result.classList.toggle('smallResult', qwen);
  unrankResult.classList.toggle('smallResult', qwen);
  byId('rankBtn').textContent = qwen ? 'Найти номер страницы' : 'Rank';
  byId('unrankBtn').textContent = qwen ? 'Открыть страницу' : 'Unrank';
  if (mode.value === 'exact_hierarchical_v1' && Number(lengthSelect.value) < 256) lengthSelect.value = '4096';
  if (mode.value === 'exact_cluster_mvp' && Number(lengthSelect.value) > 256) lengthSelect.value = '256';
  clearAddressReceipt();
  unrankResult.textContent = '';
}

async function runQwen(operation, current, output) {
  const input = operation === 'rank' ? {text: paddedPage()} : {rank: rankInput.value.trim()};
  output.textContent = 'Отправляем запрос…';
  let job = await api('/api/' + operation, {mode: QWEN_MODE, ...input});
  const id = job.job_id;
  if (!id) throw new Error('Служба не выдала номер задания.');
  while (current === revision && (job.status === 'queued' || job.status === 'running')) {
    output.textContent = job.status === 'queued' ? 'Задание в очереди…' : 'Qwen вычисляет страницу. Это может занять несколько минут.';
    await new Promise(resolve => setTimeout(resolve, 2000));
    if (current !== revision) return;
    job = await api('/api/qwen/jobs/' + encodeURIComponent(id));
    if (job.job_id !== id) throw new Error('Служба вернула ответ на другое задание.');
  }
  if (current !== revision) return;
  if (job.status !== 'done') throw new Error(job.error || 'Служба вернула неизвестное состояние задания.');
  if (operation === 'unrank') {
    setPage(job.page);
    output.textContent = job.page;
  } else {
    rankInput.value = /^0x/i.test(rankInput.value.trim()) ? job.rank_hex : job.rank;
    showAddressReceipt(job.rank, job.rank_hex);
  }
}

async function runLegacy(operation, current, output) {
  const selected = mode.value;
  const length = Number(lengthSelect.value);
  const text = query.value;
  const rank = rankInput.value;
  if (!model) model = await loadCore();
  if (current !== revision) return;
  if (operation === 'score') {
    output.textContent = show(scoreText(model, text));
  } else if (operation === 'unrank') {
    const data = selected === 'base256' ? {page: unrank(model, rank)}
      : await api('/api/unrank', {mode: selected, length, rank});
    if (current === revision) output.textContent = show(data);
  } else {
    let data;
    if (selected === 'base256') {
      const r = rankText(model, text);
      data = {...r, rankHex: '0x' + r.rank.toString(16), rankDec: r.rank.toString(), energy: 'local score only'};
    } else {
      data = await api('/api/rank', {mode: selected, length, text});
    }
    if (current !== revision) return;
    rankInput.value = data.rank_hex || data.rankHex;
    const score = scoreText(model, text);
    output.textContent = show(operation === 'search'
      ? {query: text, mode: selected, exactPagePreview: data.page.slice(0, 1024), rankHex: rankInput.value, energy: data.energy, score}
      : {...data, mode: selected, score});
  }
}

async function run(operation) {
  const current = ++revision;
  const output = operation === 'unrank' ? unrankResult : result;
  try {
    if (mode.value === QWEN_MODE) {
      clearAddressReceipt();
      setBusy(true);
      await runQwen(operation, current, output);
    } else {
      await runLegacy(operation, current, output);
    }
  } catch (error) {
    if (current === revision) output.textContent = error.message;
  } finally {
    if (current === revision) setBusy(false);
  }
}

mode.onchange = changeMode;
lengthSelect.onchange = () => {
  if (Number(lengthSelect.value) > 256) mode.value = 'exact_hierarchical_v1';
  changeMode();
};
query.oninput = () => {
  originalPage = null;
  if (mode.value === QWEN_MODE) {
    ++revision;
    clearAddressReceipt();
    updateQwenHint();
    unrankResult.textContent = '';
  }
};
rankInput.oninput = () => {
  if (decimalAddress !== null) {
    ++revision;
    clearAddressReceipt();
  }
};
query.onpaste = event => {
  if (mode.value !== QWEN_MODE || query.readOnly || query.selectionStart !== 0 ||
      query.selectionEnd !== query.value.length || !event.clipboardData) return;
  event.preventDefault();
  ++revision;
  clearAddressReceipt();
  setPage(event.clipboardData.getData('text/plain'));
  unrankResult.textContent = '';
};

byId('pageFile').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  event.target.value = '';
  const current = ++revision;
  clearAddressReceipt();
  setBusy(true);
  try {
    if (file.size > 4 * PAGE_LEN) throw new Error('Файл превышает 16 КиБ.');
    // ignoreBOM keeps an initial U+FEFF as the first character of the page.
    const page = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(await file.arrayBuffer());
    if (codePointLength(page) > PAGE_LEN) throw new Error(tooLong);
    if (current !== revision) return;
    setPage(page);
    result.textContent = 'Файл загружен.';
    unrankResult.textContent = '';
  } catch (error) {
    if (current === revision) result.textContent = error instanceof TypeError ? 'Файл содержит некорректный UTF-8.' : error.message;
  } finally {
    if (current === revision) setBusy(false);
  }
};
async function copyText(event) {
  const current = revision;
  const copyingAddress = event.currentTarget.id === 'copyAddress';
  if (copyingAddress && decimalAddress === null) return;
  try {
    await navigator.clipboard.writeText(copyingAddress ? decimalAddress : paddedPage());
    if (current === revision) result.textContent = copyingAddress ? 'Адрес скопирован.' : 'Страница скопирована.';
  } catch (error) {
    if (current !== revision) return;
    if (error instanceof TypeError || error instanceof DOMException) {
      result.textContent = copyingAddress ? 'Браузер не разрешил копирование номера.'
        : 'Браузер не разрешил копирование. Страницу можно скачать в UTF-8.';
    } else result.textContent = error.message;
  }
}
byId('copyPage').onclick = byId('copyAddress').onclick = copyText;
byId('downloadPage').onclick = () => {
  try {
    const bytes = new TextEncoder().encode(paddedPage());
    const url = URL.createObjectURL(new Blob([bytes], {type: 'text/plain;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'babel-qwen-page.txt';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    result.textContent = error.message;
  }
};
for (const name of ['score', 'rank', 'search', 'unrank']) byId(name + 'Btn').onclick = () => run(name);
if (new URLSearchParams(location.search).get('mode') === QWEN_MODE) {
  mode.value = QWEN_MODE;
  rankInput.value = '41';
}
window.addEventListener('pageshow', event => {
  if (event.persisted && mode.value === QWEN_MODE) changeMode();
});
changeMode();
