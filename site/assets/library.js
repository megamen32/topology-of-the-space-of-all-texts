let model;
const B64URL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const B64MAP = new Map([...B64URL].map((c,i)=>[c,BigInt(i)]));
const MAX_ADDR = 1n << 32768n;
const PAGE64_LEN = Math.ceil(32768 / 6); // 5462 chars. Fixed-width address before trailing-A trimming.

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
  // Page-code, not generic base64 integer.
  // Since every page is exactly 32768 bits, decoder can restore missing trailing A's.
  const full = encodeFixedPage64(n);
  const compact = full.replace(/A+$/,'');
  return compact || '∅'; // all-zero page-code: full string is AAAAA..., display as empty-set mark.
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
  if(n >= MAX_ADDR) throw new Error('page64 outside 32768-bit page space');
  return n;
}
function decimalSci(dec){
  dec = String(dec);
  if(dec.length <= 42) return dec;
  return `${dec[0]}.${dec.slice(1,18)}… × 10^${dec.length-1}`;
}
function escapeAttr(s){ return escapeHtml(String(s)).replace(/\n/g,'&#10;'); }
function decodeAddressInput(){
  const s = document.getElementById('address').value.trim() || '0';
  const mode = document.getElementById('addrFormat')?.value || 'dec';
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
  const stripped = PAGE64_LEN - (p64 === '∅' ? 0 : p64.length);
  return [
    {k:'decimal address', v:decimalSci(dec), s:'tap to expand full decimal', full:dec},
    {k:'page64', v:p64, s:`trailing A omitted: ${stripped}`, full:encodeFixedPage64(n)},
    {k:'decimal digits', v:String(dec.length)},
    {k:'page64 visible chars', v:String(p64.length)},
    {k:'page preview', v:page.slice(0,180), full:page.slice(0,1024)},
    {k:'energy / symbol', v:sc.energyPerSymbol.toFixed(2)}
  ];
}
function setAddress(n, writeMode='dec'){
  n = ((BigInt(n) % MAX_ADDR) + MAX_ADDR) % MAX_ADDR;
  const page = numberToPage(n);
  document.getElementById('addrFormat').value = writeMode;
  document.getElementById('address').value = writeMode === 'page64' ? encodePage64(n) : n.toString(10);
  document.getElementById('page').value = page;
  renderInfo(document.getElementById('addressInfo'), makeAddressItems(n,page));
  return n;
}
function randomAddress(){ const bytes=new Uint8Array(4096); crypto.getRandomValues(bytes); let n=0n; for(const b of bytes) n=(n<<8n)|BigInt(b); return n; }
async function boot(){
  model = await loadCore();
  document.getElementById('findAddress').onclick = () => {
    const page = pageFromText(model,document.getElementById('query').value);
    const n = pageToNumber(page);
    document.getElementById('addrFormat').value = 'dec';
    document.getElementById('address').value = n.toString(10);
    document.getElementById('page').value = page;
    const items = makeAddressItems(n,page);
    items.push({k:'normalized query score', v:scoreText(model,document.getElementById('query').value).energyPerSymbol.toFixed(2)});
    renderInfo(document.getElementById('searchOut'), items);
    renderInfo(document.getElementById('addressInfo'), makeAddressItems(n,page));
  };
  document.getElementById('copyAddress').onclick = async()=>{ await navigator.clipboard.writeText(document.getElementById('address').value); };
  document.getElementById('openAddress').onclick = () => { try{ setAddress(decodeAddressInput(), document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('prevPage').onclick = () => { try{ setAddress(decodeAddressInput()-1n, document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('nextPage').onclick = () => { try{ setAddress(decodeAddressInput()+1n, document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('randomPage').onclick = () => setAddress(randomAddress(),'dec');
  document.getElementById('findAddress').click();
}
boot();
