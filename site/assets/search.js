const QWEN_MODE = 'qwen_reference_v1';
const QWEN35_MODE = 'qwen35_reference_v1';
const MAX_ADDRESS = (1n << 32768n) - 1n;
const MAX_DECIMAL_DIGITS = MAX_ADDRESS.toString().length;
const isQwen = () => mode.value === QWEN_MODE || mode.value === QWEN35_MODE;
const byId = id => document.getElementById(id);
const mode = byId('rankMode');
const lengthSelect = byId('rankLength');
const query = byId('query');
const rankInput = byId('rankInput');
const result = byId('result');
const legacyUnrank = byId('legacyUnrank');
const bookStatus = byId('bookStatus');
const bookActionStatus = byId('bookActionStatus');
const reverseLookup = byId('reverseLookup');
const nativeQuerySizing = window.CSS?.supports('field-sizing', 'content');
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
let activeOperation = null;
let displayedMode = null;
let openedBook = null;
let observedUrl = null;
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
  resizeQuery();
}

function resizeQuery() {
  if (nativeQuerySizing || !reverseLookup.open) return;
  query.style.boxSizing = 'border-box';
  query.style.height = 'auto';
  query.style.height = (query.scrollHeight + query.offsetHeight - query.clientHeight) + 'px';
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

function parseAddress(value) {
  const maxLength = /^0x/i.test(value) ? 2 + 8192 : MAX_DECIMAL_DIGITS;
  if (typeof value === 'string' && value.length > maxLength) throw new Error('Слишком много цифр в номере страницы.');
  if (typeof value !== 'string' || !/^(?:[0-9]+|0x[0-9a-f]+)$/i.test(value)) {
    throw new Error('Введите десятичный номер или шестнадцатеричный номер с префиксом 0x.');
  }
  const address = BigInt(value);
  if (address > MAX_ADDRESS) throw new Error('Номер страницы превышает 2³²⁷⁶⁸ − 1.');
  return address;
}

function compactAddress(decimal) {
  const edge = 10;
  return decimal.length > 2 * edge ? decimal.slice(0, edge) + '…' + decimal.slice(-edge) : decimal;
}

function setAddressInput(address) {
  rankInput.value = /^0x/i.test(rankInput.value.trim()) ? '0x' + address.toString(16) : address.toString();
}

function showAddressReceipt(decimal, hexadecimal) {
  let preview = compactAddress(decimal);
  if (preview !== decimal) preview += '\nЦифр в номере — ' + formatCount(decimal.length);
  result.textContent = 'Адрес найден\n' + preview;
  addressFormats.textContent = 'Десятичный номер\n' + decimal + '\n\nШестнадцатеричный номер\n' + hexadecimal;
  decimalAddress = decimal;
  numberReceipt.hidden = false;
}

function updatePageButtons() {
  const busy = activeOperation !== null;
  const disabled = busy || (isQwen() && !qwenAlphabet);
  for (const id of ['rankBtn', 'copyPage', 'downloadPage']) byId(id).disabled = disabled;
  byId('prevAddress').disabled = busy || !openedBook || openedBook.address === 0n;
  byId('nextAddress').disabled = busy || !openedBook || openedBook.address === MAX_ADDRESS;
  byId('copyOpenedPage').disabled = byId('downloadOpenedPage').disabled = !openedBook;
  byId('useOpenedPage').disabled = !openedBook || query.readOnly;
}

function setOperation(operation) {
  activeOperation = operation;
  const busy = operation !== null;
  byId('unrankBtn').disabled = byId('pageFile').disabled = busy;
  byId('scoreBtn').disabled = byId('searchBtn').disabled = busy;
  rankInput.readOnly = busy;
  query.readOnly = busy && operation !== 'unrank';
  updatePageButtons();
}

const initialAddress = () => mode.value === QWEN35_MODE ? '32' : '41';

function changeMode() {
  ++revision;
  const qwen = isQwen();
  const layout = qwen ? 'qwen' : 'legacy';
  const workbench = byId('workbench');
  if (displayedMode === null || workbench.dataset.mode !== layout) reverseLookup.open = !qwen;
  if (displayedMode !== mode.value) rankInput.value = qwen ? initialAddress() : '0x0';
  displayedMode = mode.value;
  workbench.dataset.mode = layout;
  byId('readingPaper').hidden = !qwen;
  legacyUnrank.hidden = qwen;
  legacyUnrank.textContent = '';
  window.BabelReader.clear();
  openedBook = null;
  byId('pageTitle').textContent = 'Страница';
  bookStatus.textContent = bookActionStatus.textContent = '';
  for (const id of ['fileControl', 'qwenHint', 'copyPage', 'downloadPage', 'editionHint']) byId(id).hidden = !qwen;
  counterWrap.hidden = !qwen;
  byId('alphabetStatus').hidden = !qwen || Boolean(qwenAlphabet);
  if (qwen) {
    updateQwenHint();
    loadQwenAlphabet();
  } else showReplacements([]);
  for (const id of ['lengthControl', 'scoreBtn', 'searchBtn', 'clusterHint']) byId(id).hidden = qwen;
  result.classList.toggle('smallResult', qwen);
  byId('rankBtn').textContent = qwen ? 'Найти номер страницы' : 'Rank';
  byId('unrankBtn').textContent = qwen ? 'Открыть' : 'Unrank';
  if (mode.value === 'exact_hierarchical_v1' && Number(lengthSelect.value) < 256) lengthSelect.value = '4096';
  if (mode.value === 'exact_cluster_mvp' && Number(lengthSelect.value) > 256) lengthSelect.value = '256';
  clearAddressReceipt();
  setOperation(null);
  resizeQuery();
}

async function runQwen(operation, current, output, rank) {
  const requested = operation === 'unrank' ? parseAddress(rank) : null;
  const input = operation === 'rank' ? {text: paddedPage()} : {rank};
  output.textContent = 'Отправляем запрос…';
  const selectedMode = mode.value;
  const jobsPath = selectedMode === QWEN35_MODE ? '/api/qwen35/jobs/' : '/api/qwen/jobs/';
  let job = await api('/api/' + operation, {mode: selectedMode, ...input});
  const id = job.job_id;
  if (!id) throw new Error('Служба не выдала номер задания.');
  for (let poll = 0; current === revision; poll++) {
    if (job.job_id !== id || (job.mode && job.mode !== selectedMode)) {
      throw new Error('Служба вернула ответ на другое задание.');
    }
    if (job.status !== 'queued' && job.status !== 'running') break;
    output.textContent = job.status === 'queued' ? 'Задание в очереди…' : 'Qwen вычисляет страницу. Это может занять несколько минут.';
    if (poll > 0) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      if (current !== revision) return;
    }
    job = await api(jobsPath + encodeURIComponent(id));
  }
  if (current !== revision) return;
  if (job.status !== 'done') throw new Error(job.error || 'Служба вернула неизвестное состояние задания.');
  const address = parseAddress(job.rank ?? job.rank_hex ?? input.rank);
  if (requested !== null && address !== requested) throw new Error('Служба вернула другой номер страницы.');
  const page = operation === 'rank' && job.page === undefined ? input.text : job.page;
  if (typeof page !== 'string' || codePointLength(page) !== PAGE_LEN) {
    throw new Error('Служба должна вернуть страницу длиной ровно ' + pageLimit + ' знаков.');
  }
  if (operation === 'rank' && page !== input.text) throw new Error('Текст в ответе отличается от отправленной страницы.');

  const decimal = address.toString();
  window.BabelReader.show(page);
  openedBook = {address, page};
  byId('pageTitle').textContent = 'Страница ' + compactAddress(decimal);
  setAddressInput(address);
  if (operation === 'rank') showAddressReceipt(decimal, '0x' + address.toString(16));
  else clearAddressReceipt();
  bookStatus.textContent = bookActionStatus.textContent = '';
  return decimal;
}

async function runLegacy(operation, current, output, rank) {
  const selected = mode.value;
  const length = Number(lengthSelect.value);
  const text = query.value;
  if (!model) model = await loadCore();
  if (current !== revision) return;
  if (operation === 'score') {
    output.textContent = show(scoreText(model, text));
  } else if (operation === 'unrank') {
    const data = selected === 'base256' ? {page: unrank(model, rank)}
      : await api('/api/unrank', {mode: selected, length, rank});
    if (current !== revision) return;
    output.textContent = show(data);
    return data.rank ?? (rank.trim() || '0');
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

function writeLocation(rank, method) {
  const url = new URL(location.href);
  url.searchParams.set('mode', mode.value);
  url.hash = rank === null ? '' : new URLSearchParams({rank}).toString();
  if (url.href !== location.href) history[method](history.state, '', url);
  observedUrl = url.href;
}

async function run(operation, rank = rankInput.value, historyMethod = 'pushState') {
  if (activeOperation !== null) return;
  const qwen = isQwen();
  if (qwen && operation !== 'rank' && operation !== 'unrank') return;
  const current = ++revision;
  const startedAt = location.href;
  const output = operation === 'unrank' ? (qwen ? bookStatus : legacyUnrank) : result;
  setOperation(operation);
  try {
    if (qwen && operation === 'rank') {
      clearAddressReceipt();
      bookStatus.textContent = '';
    }
    const address = qwen ? await runQwen(operation, current, output, rank.trim())
      : await runLegacy(operation, current, output, rank);
    if (current === revision && address !== undefined && location.href === startedAt) {
      writeLocation(address, historyMethod);
    }
  } catch (error) {
    if (current === revision) output.textContent = error.message;
  } finally {
    if (current === revision) setOperation(null);
  }
}

function selectMode() {
  changeMode();
  writeLocation(null, 'pushState');
  if (isQwen()) run('unrank', initialAddress(), 'replaceState');
}

mode.onchange = selectMode;
byId('retryAlphabet').onclick = () => loadQwenAlphabet(true);
lengthSelect.onchange = () => {
  if (Number(lengthSelect.value) > 256) mode.value = 'exact_hierarchical_v1';
  selectMode();
};
function pageEdited() {
  resizeQuery();
  if (!isQwen()) return;
  if (activeOperation === null) {
    ++revision;
    bookStatus.textContent = '';
  }
  clearAddressReceipt();
  updateQwenHint();
}
query.onbeforeinput = () => { editStart = query.selectionStart; };
query.oninput = () => {
  if (isQwen()) {
    if (originalUnits) keepSourceLineEndings();
  } else originalUnits = null;
  editStart = null;
  pageEdited();
};
rankInput.oninput = () => {
  if (activeOperation !== null) return;
  bookStatus.textContent = '';
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
  setOperation('file');
  try {
    if (file.size > 4 * PAGE_LEN) throw new Error('Файл превышает 16 КиБ.');
    // ignoreBOM keeps an initial U+FEFF as the first character of the page.
    const page = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(await file.arrayBuffer());
    if (codePointLength(page) > PAGE_LEN) throw new Error(tooLong);
    if (current !== revision) return;
    setPage(page);
    result.textContent = 'Файл загружен.';
  } catch (error) {
    if (current === revision) result.textContent = error instanceof TypeError ? 'Файл содержит некорректный UTF-8.' : error.message;
  } finally {
    if (current === revision) setOperation(null);
  }
};
byId('useOpenedPage').onclick = () => {
  if (!openedBook || query.readOnly) return;
  if (activeOperation === null) ++revision;
  clearAddressReceipt();
  setPage(openedBook.page);
};
async function copyText(event) {
  const current = revision;
  const action = event.currentTarget.id;
  const copyingAddress = action === 'copyAddress';
  const copyingBook = action === 'copyOpenedPage';
  const address = decimalAddress;
  const book = openedBook;
  if (copyingAddress && address === null) return;
  if (copyingBook && !book) return;
  const output = copyingBook ? bookActionStatus : result;
  const stillCurrent = () => copyingBook ? book === openedBook
    : current === revision && (!copyingAddress || address === decimalAddress);
  try {
    let text;
    if (copyingAddress) text = address;
    else if (copyingBook) text = book.page;
    else text = paddedPage();
    await navigator.clipboard.writeText(text);
    if (stillCurrent()) output.textContent = copyingAddress ? 'Адрес скопирован.' : 'Страница скопирована.';
  } catch (error) {
    if (!stillCurrent()) return;
    if (error instanceof TypeError || error instanceof DOMException) {
      output.textContent = copyingAddress ? 'Браузер не разрешил копирование номера.'
        : 'Браузер не разрешил копирование. Страницу можно скачать в UTF-8.';
    } else output.textContent = error.message;
  }
}
for (const id of ['copyPage', 'copyAddress', 'copyOpenedPage']) byId(id).onclick = copyText;
function downloadText(event) {
  const fromBook = event.currentTarget.id === 'downloadOpenedPage';
  if (fromBook && !openedBook) return;
  try {
    const bytes = new TextEncoder().encode(fromBook ? openedBook.page : paddedPage());
    const url = URL.createObjectURL(new Blob([bytes], {type: 'text/plain;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'babel-qwen-page.txt';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (fromBook) bookActionStatus.textContent = 'Скачивание страницы началось.';
  } catch (error) {
    (fromBook ? bookActionStatus : result).textContent = error.message;
  }
}
byId('downloadPage').onclick = byId('downloadOpenedPage').onclick = downloadText;
for (const name of ['score', 'rank', 'search', 'unrank']) byId(name + 'Btn').onclick = () => run(name);
rankInput.onkeydown = event => {
  if (event.key !== 'Enter' || event.isComposing) return;
  event.preventDefault();
  if (!event.repeat) run('unrank');
};

function stepAddress(event, step) {
  if (event.detail > 1 || activeOperation !== null || !openedBook) return;
  const next = openedBook.address + step;
  if (next < 0n || next > MAX_ADDRESS) return;
  setAddressInput(openedBook.address);
  run('unrank', next.toString());
}
byId('prevAddress').onclick = event => stepAddress(event, -1n);
byId('nextAddress').onclick = event => stepAddress(event, 1n);
reverseLookup.addEventListener('toggle', resizeQuery);

function readLocation() {
  const url = new URL(location.href);
  if (url.href === observedUrl) return;
  observedUrl = url.href;
  const requestedMode = url.searchParams.get('mode');
  const selected = Array.from(mode.options).some(option => option.value === requestedMode)
    ? requestedMode : QWEN35_MODE;
  const rank = new URLSearchParams(url.hash.slice(1)).get('rank');
  if (selected !== displayedMode) {
    mode.value = selected;
    changeMode();
  } else {
    if (rank === null && url.hash) return; // A section link on the same page.
    ++revision;
    if (activeOperation === 'rank') clearAddressReceipt();
    bookStatus.textContent = '';
    setOperation(null);
  }
  const target = rank ?? (isQwen() ? initialAddress() : null);
  if (target === null) {
    legacyUnrank.textContent = '';
    return;
  }
  if (openedBook && target === openedBook.address.toString()) {
    rankInput.value = target;
    return;
  }
  if (!openedBook) rankInput.value = target;
  run('unrank', target, 'replaceState');
}
window.addEventListener('popstate', readLocation);
window.addEventListener('hashchange', readLocation);
window.addEventListener('pageshow', event => {
  if (event.persisted && isQwen()) {
    if (activeOperation !== 'unrank') {
      ++revision;
      setOperation(null);
    }
    clearAddressReceipt();
  }
  readLocation();
});
readLocation();
