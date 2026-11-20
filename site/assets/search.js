const QWEN_MODE = 'qwen_reference_v1';
const QWEN35_MODE = 'qwen35_reference_v1';
const isQwen = () => mode.value === QWEN_MODE || mode.value === QWEN35_MODE;
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
const plural = new Intl.PluralRules('ru-RU');
const spaceForms = {one: 'пробел', few: 'пробела', many: 'пробелов'};
const positionForms = {one: 'позиция', few: 'позиции', many: 'позиций'};
const formatCount = count => fmt(count).replaceAll('\u00a0', '\u202f');
const pageLimit = formatCount(PAGE_LEN);
const tooLong = 'Текст превышает лимит в ' + pageLimit + ' знаков.';
let model;
let revision = 0;
let originalUnits = null;
let editStart = null;
let decimalAddress = null;
let qwenAlphabet = null;
let alphabetLoading = false;

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
  originalUnits = page.includes('\r') ? textareaUnits(page) : null;
  updateQwenHint();
}

// A textarea selection counts UTF-16 units and treats CRLF as one line break.
const textareaUnits = text => text.match(/\r\n|[\s\S]/g) ?? [];
const sourceText = () => originalUnits?.join('') ?? query.value;

function replaceSourceRange(start, end, replacement) {
  const units = originalUnits ?? query.value.split('');
  const edited = units.slice(0, start).concat(textareaUnits(replacement), units.slice(end));
  originalUnits = edited.some(unit => unit.startsWith('\r')) ? edited : null;
}

function keepSourceLineEndings() {
  // Retain the original breaks on either side of a native edit, including
  // adjacent breaks that look identical in the textarea but differ in the file.
  const before = originalUnits.map(unit => unit.startsWith('\r') ? '\n' : unit).join('');
  const after = query.value;
  const startLimit = Math.min(editStart ?? query.selectionStart, query.selectionStart, before.length);
  let start = 0;
  while (start < startLimit && before[start] === after[start]) start++;
  let oldEnd = before.length;
  let newEnd = after.length;
  while (oldEnd > start && newEnd > query.selectionEnd && before[oldEnd - 1] === after[newEnd - 1]) {
    oldEnd--;
    newEnd--;
  }
  replaceSourceRange(start, oldEnd, after.slice(start, newEnd));
}

function codePointLength(text) {
  let count = 0;
  for (const _ of text) count++;
  return count;
}

async function loadQwenAlphabet(reload = false) {
  if (qwenAlphabet || alphabetLoading) return;
  alphabetLoading = true;
  const message = byId('alphabetMessage');
  const retry = byId('retryAlphabet');
  message.textContent = 'Загружаем алфавит для поиска, копирования и скачивания…';
  retry.hidden = true;
  try {
    const response = await fetch('/api/qwen/alphabet', {cache: reload ? 'reload' : 'default'});
    if (!response.ok) throw new Error();
    const {alphabet} = await response.json();
    const symbols = new Set(alphabet);
    if (typeof alphabet !== 'string' || codePointLength(alphabet) !== 256 || symbols.size !== 256 || !symbols.has(' ')) {
      throw new Error();
    }
    qwenAlphabet = symbols;
  } catch {
    message.textContent = 'Для поиска, копирования и скачивания нужен алфавит издания. Загрузить его не удалось.';
    retry.hidden = false;
  } finally {
    alphabetLoading = false;
  }
  if (qwenAlphabet && isQwen()) {
    byId('alphabetStatus').hidden = true;
    updateQwenHint();
    updatePageButtons();
  }
}

function prepareQwenPage() {
  const text = sourceText();
  const count = codePointLength(text);
  const replacements = [];
  if (count > PAGE_LEN) return {count, replacements, error: tooLong};
  if (/[\uD800-\uDFFF]/u.test(text)) return {count, replacements, error: 'Текст содержит недопустимый символ Unicode.'};
  if (!qwenAlphabet) return {count, replacements};

  let page = '';
  let position = 0;
  for (const symbol of text) {
    position++;
    if (qwenAlphabet.has(symbol)) page += symbol;
    else {
      replacements.push({position, symbol});
      page += ' ';
    }
  }
  return {count, replacements, page: page + ' '.repeat(PAGE_LEN - count)};
}

function paddedPage() {
  const {page, error} = prepareQwenPage();
  if (page === undefined) throw new Error(error || 'Сначала загрузите алфавит издания.');
  return page;
}

const symbolNames = {
  '\0': 'нулевой символ', '\t': 'табуляция', '\v': 'вертикальная табуляция',
  '\f': 'перевод страницы', '\r': 'возврат каретки (CR)', '\u0085': 'переход на следующую строку',
  '\u00A0': 'неразрывный пробел', '\u00AD': 'мягкий перенос', '\u1680': 'огамический пробел',
  '\u2000': 'пробел в половину кегля', '\u2001': 'пробел в один кегль',
  '\u2002': 'пробел в половину кегля', '\u2003': 'пробел в один кегль',
  '\u2004': 'пробел в треть кегля', '\u2005': 'пробел в четверть кегля', '\u2006': 'пробел в шестую часть кегля',
  '\u2007': 'цифровой пробел', '\u2008': 'пунктуационный пробел', '\u2009': 'тонкий пробел',
  '\u200A': 'волосяной пробел', '\u200C': 'запрет соединения соседних знаков',
  '\u2028': 'разделитель строк', '\u2029': 'разделитель абзацев', '\u202F': 'узкий неразрывный пробел',
  '\u205F': 'средний математический пробел', '\u2060': 'неразрывный соединитель слов',
  '\u3000': 'идеографический пробел',
};

function symbolName(symbol) {
  if (symbolNames[symbol]) return symbolNames[symbol];
  if (/\p{Bidi_Control}/u.test(symbol)) return 'знак направления письма';
  if (/\p{Variation_Selector}/u.test(symbol)) return 'селектор варианта начертания';
  if (/[\p{Default_Ignorable_Code_Point}\p{Cf}]/u.test(symbol)) return 'невидимый знак форматирования';
  if (/\p{Cc}/u.test(symbol)) return 'управляющий символ';
  if (/\p{Mark}/u.test(symbol)) return 'комбинируемый знак';
  return '';
}

function replacementItem({position, symbol}) {
  const item = document.createElement('li');
  const glyph = document.createElement('bdi');
  glyph.textContent = symbol;
  const name = symbolName(symbol);
  item.append('Позиция ' + position + ' — ', glyph, ' ' + codeInfo(symbol), name ? ' (' + name + ')' : '');
  return item;
}

function showReplacements(replacements) {
  const count = replacements.length;
  const previewLimit = 3;
  byId('qwenReplacements').hidden = count === 0;
  const hint = byId('replacementHint');
  const summary = count ? 'Знаков вне алфавита — ' + formatCount(count)
    + '. При поиске, копировании и скачивании каждый заменим обычным пробелом (U+0020).' : '';
  if (hint.textContent !== summary) hint.textContent = summary;
  byId('replacementPreview').replaceChildren(...replacements.slice(0, previewLimit).map(replacementItem));

  const more = byId('moreReplacements');
  const rest = count - previewLimit;
  more.hidden = rest <= 0;
  if (more.hidden) more.open = false;
  byId('morePositions').textContent = rest > 0 ? 'Ещё ' + formatCount(rest) + ' ' + positionForms[plural.select(rest)] : '';
  // Build the rest only when expanded, including when the user edits an open list.
  const renderList = () => {
    const entries = more.open ? replacements.slice(previewLimit).map(replacementItem) : [];
    byId('replacementList').replaceChildren(...entries);
  };
  more.ontoggle = renderList;
  renderList();
}

function updateQwenHint() {
  const {count, replacements, error} = prepareQwenPage();
  const remaining = PAGE_LEN - count;
  charCount.textContent = formatCount(count) + ' / ' + pageLimit;
  counterWrap.classList.toggle('over-limit', remaining < 0);
  const hint = byId('qwenHint');
  if (error) hint.textContent = error;
  else if (remaining === 0) hint.textContent = 'Страница полная.';
  else hint.textContent = 'Справа добавим ' + formatCount(remaining) + ' ' + spaceForms[plural.select(remaining)] + '.';
  showReplacements(replacements);
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

function updatePageButtons() {
  const disabled = query.readOnly || (isQwen() && !qwenAlphabet);
  for (const id of ['rankBtn', 'copyPage', 'downloadPage']) byId(id).disabled = disabled;
}

function setBusy(busy) {
  byId('unrankBtn').disabled = byId('pageFile').disabled = busy;
  query.readOnly = rankInput.readOnly = busy;
  updatePageButtons();
}

function changeMode() {
  ++revision;
  setBusy(false);
  const qwen = isQwen();
  for (const id of ['fileControl', 'qwenHint', 'copyPage', 'downloadPage', 'editionHint']) byId(id).hidden = !qwen;
  counterWrap.hidden = !qwen;
  byId('alphabetStatus').hidden = !qwen || Boolean(qwenAlphabet);
  if (qwen) {
    updateQwenHint();
    loadQwenAlphabet();
  } else showReplacements([]);
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
  const selectedMode = mode.value;
  const jobsPath = selectedMode === QWEN35_MODE ? '/api/qwen35/jobs/' : '/api/qwen/jobs/';
  let job = await api('/api/' + operation, {mode: selectedMode, ...input});
  const id = job.job_id;
  if (!id) throw new Error('Служба не выдала номер задания.');
  for (let poll = 0; current === revision && (job.status === 'queued' || job.status === 'running'); poll++) {
    output.textContent = job.status === 'queued' ? 'Задание в очереди…' : 'Qwen вычисляет страницу. Это может занять несколько минут.';
    if (poll > 0) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      if (current !== revision) return;
    }
    job = await api(jobsPath + encodeURIComponent(id));
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
    if (isQwen()) {
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
byId('retryAlphabet').onclick = () => loadQwenAlphabet(true);
lengthSelect.onchange = () => {
  if (Number(lengthSelect.value) > 256) mode.value = 'exact_hierarchical_v1';
  changeMode();
};
function pageEdited() {
  ++revision;
  clearAddressReceipt();
  updateQwenHint();
  unrankResult.textContent = '';
}
query.onbeforeinput = () => { editStart = query.selectionStart; };
query.oninput = () => {
  if (isQwen()) {
    if (originalUnits) keepSourceLineEndings();
    pageEdited();
  } else originalUnits = null;
  editStart = null;
};
rankInput.oninput = () => {
  if (decimalAddress !== null) {
    ++revision;
    clearAddressReceipt();
  }
};
query.onpaste = event => {
  if (!isQwen() || query.readOnly || !event.clipboardData) return;
  const pasted = event.clipboardData.getData('text/plain');
  const start = query.selectionStart;
  const end = query.selectionEnd;
  const replaceAll = start === 0 && end === query.value.length;
  if (!replaceAll && !pasted.includes('\r')) return;
  event.preventDefault();
  if (replaceAll) originalUnits = pasted.includes('\r') ? textareaUnits(pasted) : null;
  else replaceSourceRange(start, end, pasted);
  query.setRangeText(pasted.replace(/\r\n?/g, '\n'), start, end, 'end');
  pageEdited();
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
const requestedMode = new URLSearchParams(location.search).get('mode');
if (requestedMode === QWEN_MODE || requestedMode === QWEN35_MODE) {
  mode.value = requestedMode;
  rankInput.value = '41';
}
window.addEventListener('pageshow', event => {
  if (event.persisted && isQwen()) changeMode();
});
changeMode();
