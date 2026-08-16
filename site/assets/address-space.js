const $ = (id) => document.getElementById(id);

function formatAddress(value) {
  const text = String(value || '');
  if (text.length <= 56) return text;
  return `${text.slice(0, 28)}…${text.slice(-22)}`;
}

function facts(items) {
  return `<dl>${items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
}

async function post(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `API ${response.status}`);
  return data;
}

function setResult(title, html) {
  $('locateStatus').textContent = title;
  $('locateFacts').innerHTML = html;
}

async function locateRaw() {
  const text = $('addressText').value;
  setResult('Вычисляю полный raw-address…', '<p>Ранжирование 4096-символьной страницы.</p>');
  try {
    const data = await post('/api/rank', {text});
    setResult('Полная координата найдена', facts([
      ['HEX ADDRESS', `<code title="${data.rank_hex}">${formatAddress(data.rank_hex)}</code>`],
      ['DECIMAL DIGITS', String(data.rank_dec).length],
      ['PAGE RULE', 'normalise → pad to 4096 → base-256']
    ]));
  } catch (error) { setResult('Не удалось вычислить адрес', `<p>${error.message}</p>`); }
}

async function locateSemantic() {
  const text = $('addressText').value;
  setResult('Считаю exact semantic rank…', '<p>Точный energy-order для первых 256 символов страницы.</p>');
  try {
    const data = await post('/api/rank', {mode: 'exact_cluster_mvp', length: 256, text});
    setResult('Exact semantic address найден', facts([
      ['ENERGY', String(data.energy)],
      ['EXACT RANK', `<code title="${data.rank_hex}">${formatAddress(data.rank_hex)}</code>`],
      ['ORDER', 'cluster-energy → raw tie-break'],
      ['SCOPE', 'exact for all pages of length 256']
    ]));
  } catch (error) { setResult('Не удалось вычислить semantic rank', `<p>${error.message}</p>`); }
}

async function openRaw() {
  const rank = $('rankInput').value.trim();
  $('pageResult').textContent = 'Открываю страницу…';
  try {
    const data = await post('/api/unrank', {rank});
    const page = data.preview || data.text || '';
    // Page zero is a valid page made entirely of padding spaces. Render those
    // spaces visibly so opening the first exact address does not look broken.
    $('pageResult').textContent = page.replaceAll(' ', '·');
  } catch (error) { $('pageResult').textContent = `Ошибка: ${error.message}`; }
}

$('rawLocate').addEventListener('click', locateRaw);
$('semanticLocate').addEventListener('click', locateSemantic);
$('openRaw').addEventListener('click', openRaw);
