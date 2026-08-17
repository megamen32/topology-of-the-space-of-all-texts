let model;
let babelRank = null;
let babelRouteIndex = null;
let catalogueRank = null;
const B64URL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const B64MAP = new Map([...B64URL].map((c,i)=>[c,BigInt(i)]));
const MAX_ADDR = 1n << 32768n;
const PAGE64_LEN = Math.ceil(32768 / 6); // 5462 fixed symbols before right-side vacuum trim

function encodeFixedPage64(n){
  n = BigInt(n);
  if(n < 0n || n >= MAX_ADDR) throw new Error('address out of [0, 2^32768)');
  let out = '';
  for(let i=0;i<PAGE64_LEN;i++){
    out = B64URL[Number(n & 63n)] + out;
    n >>= 6n;
  }
  return out;
}
function encodePage64(n){
  const full = encodeFixedPage64(n);
  const compact = full.replace(/A+$/,'');
  return compact || '∅';
}
function decodePage64(s){
  s = String(s).trim();
  if(!s || s === '∅' || s === '0') s = '';
  if(s.length > PAGE64_LEN) throw new Error('page64 too long');
  s = s.padEnd(PAGE64_LEN, 'A');
  let n = 0n;
  for(const ch of s){
    if(!B64MAP.has(ch)) throw new Error('bad page64 char: '+ch);
    n = (n << 6n) | B64MAP.get(ch);
  }
  if(n >= MAX_ADDR) throw new Error('page64 outside page space');
  return n;
}
function decimalSci(dec){
  dec = String(dec);
  if(dec.length <= 42) return dec;
  return `${dec[0]}.${dec.slice(1,18)}… × 10^${dec.length-1}`;
}
function escapeAttr(s){ return escapeHtml(String(s)).replace(/\n/g,'&#10;'); }
function visiblePage64FromCurrent(){
  const mode = document.getElementById('addrFormat')?.value || 'page64';
  const raw = document.getElementById('address').value.trim();
  if(mode === 'page64') return raw && raw !== '0' ? raw : '∅';
  try { return encodePage64(BigInt(raw.replace(/\s+/g,''))); } catch { return '∅'; }
}
function visibleStepFromPage64(p64){
  let s = String(p64).trim();
  if(!s || s === '∅' || s === '0') s = '';
  if(s.length > PAGE64_LEN) throw new Error('page64 too long');
  const hiddenA = PAGE64_LEN - s.length;
  return 1n << BigInt(6 * hiddenA);
}
function decodeAddressInput(){
  const s = document.getElementById('address').value.trim() || '0';
  const mode = document.getElementById('addrFormat')?.value || 'page64';
  let n = mode === 'page64' ? decodePage64(s) : BigInt(s.replace(/\s+/g,''));
  if(n < 0n || n >= MAX_ADDR) throw new Error('address out of [0, 2^32768)');
  return n;
}
function pageToNumber(page){ let n=0n; for(const ch of page){ n=(n<<8n)|BigInt(model.index.get(ch) ?? 0); } return n; }
function numberToPage(n){ n=BigInt(n); const arr=new Array(PAGE_LEN); for(let i=PAGE_LEN-1;i>=0;i--){ arr[i]=model.alphabet[Number(n&255n)]||' '; n >>= 8n; } return arr.join(''); }
function metricCard(k,display,small='',full=''){
  const fullAttr = full ? ` data-full="${escapeAttr(full)}"` : '';
  return `<div class="metric${full?' expandable':''}"${fullAttr}><div class="metricK">${escapeHtml(k)}</div><div class="metricV">${escapeHtml(display)}</div><div class="metricS">${escapeHtml(small||'')}</div></div>`;
}
function attachExpand(root){
  root.querySelectorAll('.metric.expandable').forEach(card=>{
    const v = card.querySelector('.metricV');
    const short = v.textContent;
    const full = card.dataset.full;
    let open = false;
    card.onclick = () => { open = !open; v.textContent = open ? full : short; card.classList.toggle('open', open); };
  });
}
function renderInfo(el,items){
  el.innerHTML = '<div class="metricGrid">' + items.map(x=>metricCard(x.k,x.v,x.s,x.full)).join('') + '</div>';
  attachExpand(el);
}
function makeAddressItems(n,page){
  const sc = scoreText(model,page.slice(0,1024));
  const dec = n.toString(10);
  const p64 = encodePage64(n);
  const visible = p64 === '∅' ? 0 : p64.length;
  const hidden = PAGE64_LEN - visible;
  return [
    {k:'page64', v:p64, s:`скрытых завершающих A: ${hidden}`, full:encodeFixedPage64(n)},
    {k:'десятичный адрес', v:decimalSci(dec), s:'нажмите, чтобы раскрыть целиком', full:dec},
    {k:'шаг навигации', v:`64^${hidden}`, s:'меняет последний видимый знак page64'},
    {k:'начало страницы', v:page.slice(0,180), full:page.slice(0,1024)},
    {k:'стоимость / знак', v:sc.energyPerSymbol.toFixed(2)}
  ];
}
function makeBabelItems(result){
  const rank = String(result.rank);
  const items = [
    {k:'издание', v:'Babel-1', s:'точная обратимая нумерация'},
    {k:'номер Babel-1', v:decimalSci(rank), s:'нажмите, чтобы раскрыть целиком', full:rank},
    {k:'шестнадцатеричный номер', v:result.rank_hex.slice(0,42)+'…', full:result.rank_hex},
    {k:'оболочка', v:String(result.shell), s:'сколько позиций использовало редкие слоты'},
    {k:'что гарантировано', v:'биекция', s:'языковое сходство — открытая проверяемая гипотеза'}
  ];
  if(result.route){
    items.unshift({k:'читательский маршрут',v:`${Number(result.route_index)+1} / ${result.route_total}`,s:`${result.author}: ${result.source_text}`});
  }
  return items;
}
function makeCatalogueItems(result){
  const rank = String(result.rank);
  return [
    {k:'режим', v:'читаемое начало', s:'конечный каталог русских абзацев'},
    {k:'точный номер', v:rank, s:`первые ${result.structured_pages} номера — catalogue-MVP`},
    {k:'тип страницы', v:result.page_kind === 'structured_catalogue' ? 'читаемая страница' : 'raw fallback', s:result.page_kind === 'structured_catalogue' ? 'две страницы каталога' : 'обычная страница полного пространства'},
    {k:'что гарантировано', v:'полная биекция', s:result.ordering_note},
    {k:'абзацев в каталоге', v:String(result.paragraphs), s:`${result.structured_pages} двухабзацных страниц`},
  ];
}
function setRawNavLabels(){
  document.getElementById('prevPage').textContent = '← Предыдущая';
  document.getElementById('nextPage').textContent = 'Следующая →';
}
function setAddress(n, writeMode='page64'){
  babelRank = null;
  babelRouteIndex = null;
  catalogueRank = null;
  n = ((BigInt(n) % MAX_ADDR) + MAX_ADDR) % MAX_ADDR;
  const page = numberToPage(n);
  document.getElementById('addrFormat').value = writeMode;
  const visibleAddress = writeMode === 'page64' ? encodePage64(n) : n.toString(10);
  document.getElementById('address').value = visibleAddress;
  const currentShort = document.getElementById('currentShort');
  if(currentShort) currentShort.textContent = writeMode === 'page64' ? visibleAddress : decimalSci(visibleAddress);
  document.getElementById('readerFormat').textContent = 'обычный адрес';
  setRawNavLabels();
  document.getElementById('page').value = page;
  renderInfo(document.getElementById('addressInfo'), makeAddressItems(n,page));
  return n;
}
function randomAddress(){ const bytes=new Uint8Array(4096); crypto.getRandomValues(bytes); let n=0n; for(const b of bytes) n=(n<<8n)|BigInt(b); return n; }
function niceNav(delta){
  if(catalogueRank !== null){
    return openCatalogueRank((catalogueRank + BigInt(delta) + MAX_ADDR) % MAX_ADDR);
  }
  if(babelRouteIndex !== null){
    return openReadingRoute(babelRouteIndex + delta);
  }
  if(babelRank !== null){
    return openBabelRank((babelRank + BigInt(delta) + MAX_ADDR) % MAX_ADDR);
  }
  const n = decodeAddressInput();
  const p64 = visiblePage64FromCurrent();
  const step = visibleStepFromPage64(p64);
  // Always navigate at the visible page64 scale. This makes B263 -> B264, and backwards B263 -> B262.
  setAddress(n + BigInt(delta) * step, 'page64');
}
async function babelApi(path, payload){
  const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || `API ${response.status}`);
  return result;
}
function showBabel(result){
  catalogueRank = null;
  babelRank = BigInt(result.rank);
  babelRouteIndex = result.route ? Number(result.route_index) : null;
  document.getElementById('babelAddress').value = result.rank;
  document.getElementById('page').value = result.page;
  document.getElementById('currentShort').textContent = `Babel-1: ${decimalSci(result.rank)}`;
  document.getElementById('readerFormat').textContent = result.route ? `Читательский маршрут · ${result.author}` : `Babel-1 · оболочка ${result.shell}`;
  document.getElementById('prevPage').textContent = result.route ? '← Предыдущая в маршруте' : '← Точный номер −1';
  document.getElementById('nextPage').textContent = result.route ? 'Следующая в маршруте →' : 'Точный номер +1 →';
  renderInfo(document.getElementById('babelOut'), makeBabelItems(result));
  renderInfo(document.getElementById('addressInfo'), makeBabelItems(result));
}
function showCatalogue(result){
  catalogueRank = BigInt(result.rank);
  babelRank = null;
  babelRouteIndex = null;
  document.getElementById('catalogueAddress').value = result.rank;
  document.getElementById('page').value = result.page;
  document.getElementById('currentShort').textContent = `Каталог: ${result.rank}`;
  document.getElementById('readerFormat').textContent = result.page_kind === 'structured_catalogue'
    ? 'читаемое начало · точный каталог'
    : 'точный raw fallback';
  document.getElementById('prevPage').textContent = '← Точный номер −1';
  document.getElementById('nextPage').textContent = 'Точный номер +1 →';
  renderInfo(document.getElementById('catalogueOut'), makeCatalogueItems(result));
  renderInfo(document.getElementById('addressInfo'), makeCatalogueItems(result));
}
async function openCatalogueRank(rank){
  const result = await babelApi('/api/unrank',{mode:'hierarchical_catalogue_v1',rank:String(rank)});
  showCatalogue(result);
}
async function openBabelRank(rank){
  const result = await babelApi('/api/unrank',{mode:'babel_1_shell',rank:String(rank)});
  showBabel(result);
}
async function openReadingRoute(index){
  const result = await babelApi('/api/babel-1-route',{index});
  showBabel(result);
}
async function boot(){
  model = await loadCore();
  document.getElementById('findAddress').onclick = () => {
    babelRank = null; babelRouteIndex = null; setRawNavLabels();
    const page = pageFromText(model,document.getElementById('query').value);
    const n = pageToNumber(page);
    // Product default: show page64, decimal as secondary expandable card.
    document.getElementById('addrFormat').value = 'page64';
    const visibleAddress = encodePage64(n);
    document.getElementById('address').value = visibleAddress;
    const currentShort = document.getElementById('currentShort');
    if(currentShort) currentShort.textContent = visibleAddress;
    document.getElementById('page').value = page;
    const items = makeAddressItems(n,page);
    items.push({k:'стоимость нормализованного запроса', v:scoreText(model,document.getElementById('query').value).energyPerSymbol.toFixed(2)});
    renderInfo(document.getElementById('searchOut'), items);
    renderInfo(document.getElementById('addressInfo'), makeAddressItems(n,page));
  };
  document.getElementById('copyAddress').onclick = async()=>{ await navigator.clipboard.writeText(document.getElementById('address').value); };
  document.getElementById('openAddress').onclick = () => { try{ setAddress(decodeAddressInput(), document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('prevPage').onclick = () => { try{ niceNav(-1); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('nextPage').onclick = () => { try{ niceNav(1); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('randomPage').onclick = () => setAddress(randomAddress(),'page64');
  document.getElementById('openCatalogueAddress').onclick = async () => {
    try { await openCatalogueRank(document.getElementById('catalogueAddress').value.trim() || '0'); }
    catch(e){ document.getElementById('catalogueOut').textContent=String(e); }
  };
  document.getElementById('findBabelAddress').onclick = async () => {
    try { showBabel(await babelApi('/api/rank',{mode:'babel_1_shell',text:document.getElementById('query').value})); }
    catch(e){ document.getElementById('babelOut').textContent=String(e); }
  };
  document.getElementById('openBabelAddress').onclick = async () => {
    try { await openBabelRank(document.getElementById('babelAddress').value.trim() || '0'); }
    catch(e){ document.getElementById('babelOut').textContent=String(e); }
  };
  await openCatalogueRank(0);
}
boot();
