const QWEN_MODE = 'qwen_reference_v1';
const byId = id => document.getElementById(id);
const mode = byId('rankMode');
const lengthSelect = byId('rankLength');
const query = byId('query');
const rankInput = byId('rankInput');
const result = byId('result');
const unrankResult = byId('unrankResult');
let model;
let revision = 0;
let originalPage = null;

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
}

function exactPage() {
  const page = originalPage ?? query.value;
  if (page.length > 2 * PAGE_LEN || [...page].length !== PAGE_LEN) throw new Error('Нужна страница ровно из 4096 знаков.');
  return page;
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
  for (const id of ['lengthControl', 'scoreBtn', 'searchBtn', 'clusterHint']) byId(id).hidden = qwen;
  result.classList.toggle('smallResult', qwen);
  unrankResult.classList.toggle('smallResult', qwen);
  byId('rankBtn').textContent = qwen ? 'Найти номер страницы' : 'Rank';
  byId('unrankBtn').textContent = qwen ? 'Открыть страницу' : 'Unrank';
  if (mode.value === 'exact_hierarchical_v1' && Number(lengthSelect.value) < 256) lengthSelect.value = '4096';
  if (mode.value === 'exact_cluster_mvp' && Number(lengthSelect.value) > 256) lengthSelect.value = '256';
  result.textContent = unrankResult.textContent = '';
}

async function runQwen(operation, current, output) {
  const input = operation === 'rank' ? {text: exactPage()} : {rank: rankInput.value.trim()};
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
    result.textContent = '';
    output.textContent = job.page;
  } else {
    rankInput.value = /^0x/i.test(rankInput.value.trim()) ? job.rank_hex : job.rank;
    output.textContent = 'Десятичный номер\n' + job.rank + '\n\nШестнадцатеричный номер\n' + job.rank_hex;
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
  if (mode.value === QWEN_MODE) result.textContent = unrankResult.textContent = '';
};
query.onpaste = event => {
  if (mode.value !== QWEN_MODE || query.readOnly || query.selectionStart !== 0 ||
      query.selectionEnd !== query.value.length || !event.clipboardData) return;
  event.preventDefault();
  setPage(event.clipboardData.getData('text/plain'));
  result.textContent = unrankResult.textContent = '';
};

byId('pageFile').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  event.target.value = '';
  const current = ++revision;
  setBusy(true);
  try {
    if (file.size > 4 * PAGE_LEN) throw new Error('Файл превышает 16 КиБ.');
    // ignoreBOM keeps an initial U+FEFF as the first character of the page.
    const page = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(await file.arrayBuffer());
    if ([...page].length !== PAGE_LEN) throw new Error('В файле должно быть ровно 4096 знаков.');
    if (current !== revision) return;
    setPage(page);
    result.textContent = 'Загружены все 4096 знаков.';
    unrankResult.textContent = '';
  } catch (error) {
    if (current === revision) result.textContent = error instanceof TypeError ? 'Файл содержит некорректный UTF-8.' : error.message;
  } finally {
    if (current === revision) setBusy(false);
  }
};
byId('copyPage').onclick = async () => {
  const current = revision;
  try {
    const page = exactPage();
    await navigator.clipboard.writeText(page);
    if (current === revision) result.textContent = 'Страница скопирована.';
  } catch (error) {
    if (current === revision) result.textContent = error instanceof TypeError || error instanceof DOMException
      ? 'Браузер не разрешил копирование. Страницу можно скачать в UTF-8.' : error.message;
  }
};
byId('downloadPage').onclick = () => {
  try {
    const bytes = new TextEncoder().encode(exactPage());
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
if (new URLSearchParams(location.search).get('mode') === QWEN_MODE) mode.value = QWEN_MODE;
changeMode();
