let model;
const B64URL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const B64MAP = new Map([...B64URL].map((c,i)=>[c,BigInt(i)]));
const MAX_ADDR = 1n << 32768n;

function encodeB64u(n){
  n = BigInt(n);
  if(n < 0n) throw new Error('negative address');
  if(n === 0n) return '0';
  let out='';
  while(n > 0n){ out = B64URL[Number(n & 63n)] + out; n >>= 6n; }
  return out;
}
function decodeB64u(s){
  s=String(s).trim();
  if(!s || s==='0') return 0n;
  let n=0n;
  for(const ch of s){
    if(!B64MAP.has(ch)) throw new Error('bad base64url char: '+ch);
    n=(n<<6n)|B64MAP.get(ch);
  }
  if(n >= MAX_ADDR) throw new Error('address out of 2^32768 space');
  return n;
}
function shortMiddle(s, left=24, right=18){
  s=String(s);
  if(s.length <= left+right+3) return s;
  return s.slice(0,left)+'…'+s.slice(-right);
}
function decodeAddressInput(){
  const s=document.getElementById('address').value.trim() || '0';
  const mode=document.getElementById('addrFormat')?.value || 'dec';
  let n;
  if(mode === 'b64') n=decodeB64u(s);
  else n=BigInt(s.replace(/\s+/g,''));
  if(n<0n || n>=MAX_ADDR) throw new Error('address out of [0, 2^32768)');
  return n;
}
function pageToNumber(page){ let n=0n; for(const ch of page){ n=(n<<8n)|BigInt(model.index.get(ch) ?? 0); } return n; }
function numberToPage(n){ n=BigInt(n); const arr=new Array(PAGE_LEN); for(let i=PAGE_LEN-1;i>=0;i--){ arr[i]=model.alphabet[Number(n&255n)]||' '; n >>= 8n; } return arr.join(''); }
function metricCard(k,v,small=''){ return `<div class="metric"><div class="metricK">${k}</div><div class="metricV">${v}</div><div class="metricS">${small||''}</div></div>`; }
function renderInfo(el,obj){
  el.innerHTML='';
  const wrap=document.createElement('div'); wrap.className='metricGrid';
  for(const [k,v] of Object.entries(obj)){
    if(typeof v === 'object' && v){
      wrap.innerHTML += metricCard(k, `<pre>${escapeHtml(JSON.stringify(v,null,2))}</pre>`);
    } else {
      wrap.innerHTML += metricCard(k, escapeHtml(String(v)));
    }
  }
  el.appendChild(wrap);
}
function addressInfo(n,page){
  const sc=scoreText(model,page.slice(0,1024));
  const dec=n.toString(10);
  const b64=encodeB64u(n);
  return {
    decimalAddressPreview: shortMiddle(dec,32,24),
    compactBase64urlPreview: shortMiddle(b64,28,20),
    decimalDigits: dec.length,
    base64urlChars: b64.length,
    pagePreview: page.slice(0,180),
    previewEnergyPerSymbol: sc.energyPerSymbol.toFixed(2)
  };
}
function setAddress(n, writeMode='dec'){
  n = ((BigInt(n) % MAX_ADDR) + MAX_ADDR) % MAX_ADDR;
  const page=numberToPage(n);
  document.getElementById('addrFormat').value=writeMode;
  document.getElementById('address').value=writeMode==='b64' ? encodeB64u(n) : n.toString(10);
  document.getElementById('page').value=page;
  renderInfo(document.getElementById('addressInfo'), addressInfo(n,page));
  return n;
}
function randomAddress(){ const bytes=new Uint8Array(4096); crypto.getRandomValues(bytes); let n=0n; for(const b of bytes) n=(n<<8n)|BigInt(b); return n; }
async function boot(){
  model=await loadCore();
  document.getElementById('findAddress').onclick=()=>{
    const page=pageFromText(model,document.getElementById('query').value);
    const n=pageToNumber(page);
    document.getElementById('addrFormat').value='dec';
    document.getElementById('address').value=n.toString(10);
    document.getElementById('page').value=page;
    renderInfo(document.getElementById('searchOut'), {
      decimalAddressPreview: shortMiddle(n.toString(10),32,24),
      compactBase64urlPreview: shortMiddle(encodeB64u(n),28,20),
      normalizedPreview: page.slice(0,180),
      energyPerSymbol: scoreText(model,document.getElementById('query').value).energyPerSymbol.toFixed(2)
    });
    renderInfo(document.getElementById('addressInfo'), addressInfo(n,page));
  };
  document.getElementById('copyAddress').onclick=async()=>{ await navigator.clipboard.writeText(document.getElementById('address').value); };
  document.getElementById('openAddress').onclick=()=>{ try{ setAddress(decodeAddressInput(), document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('prevPage').onclick=()=>{ try{ setAddress(decodeAddressInput()-1n, document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('nextPage').onclick=()=>{ try{ setAddress(decodeAddressInput()+1n, document.getElementById('addrFormat').value); }catch(e){ document.getElementById('addressInfo').textContent=String(e); } };
  document.getElementById('randomPage').onclick=()=>setAddress(randomAddress(),'dec');
  document.getElementById('findAddress').click();
}
boot();
