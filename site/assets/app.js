let model;

function mulberry32(seed){
  let t = seed >>> 0;
  return function(){
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ t >>> 15, 1 | t);
    r ^= r + Math.imul(r ^ r >>> 7, 61 | r);
    return ((r ^ r >>> 14) >>> 0) / 4294967296;
  }
}

function hashSeed(s){
  let h = 2166136261;
  for (const ch of String(s)) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function weightedChoice(counter, rng, temperature=0.82){
  const entries = Object.entries(counter || {});
  if (!entries.length) return null;
  let weights = entries.map(([k,v]) => [k, Math.pow(Number(v), temperature)]);
  let total = weights.reduce((a,[,w]) => a+w,0);
  let x = rng()*total;
  for (const [k,w] of weights){ x -= w; if (x <= 0) return k; }
  return weights[weights.length-1][0];
}

function generatePage(seed, len){
  const rng = mulberry32(hashSeed(seed));
  let cls = 'START';
  let out = '';
  let repeatSpace = 0;
  let repeatEmoji = 0;
  for (let i=0;i<len;i++){
    let nextCls = weightedChoice(model.transitions[cls] || model.transitions.START, rng, 0.62) || 'SPACE';
    // anti-collapse v0
    if (nextCls === 'SPACE' && repeatSpace > 0) nextCls = rng() < 0.55 ? 'RU' : 'EN';
    if (nextCls === 'EMOJI' && repeatEmoji > 3) nextCls = 'SPACE';
    const ch = weightedChoice(model.emissions[nextCls], rng, 0.76) || ' ';
    out += ch;
    repeatSpace = ch === ' ' ? repeatSpace + 1 : 0;
    repeatEmoji = nextCls === 'EMOJI' ? repeatEmoji + 1 : 0;
    cls = nextCls;
  }
  return out;
}

async function boot(){
  model = await fetch('data/model.json').then(r => r.json());
  document.getElementById('coverage').textContent = (model.coverage*100).toFixed(4)+'%';
  document.getElementById('classes').textContent = new Set(Object.values(model.symbol_class)).size;
  document.getElementById('alphabet').innerHTML = model.alphabet.map(ch => `<span title="${escapeHtml(ch)}">${escapeHtml(ch)}</span>`).join('');
  document.getElementById('emoji').innerHTML = model.emoji_top.slice(0,40).map(([ch,n]) => `<span title="${n}">${escapeHtml(ch)}</span>`).join('');
  document.getElementById('generate').onclick = () => {
    const seed = document.getElementById('seed').value;
    const len = Math.max(32, Math.min(4096, Number(document.getElementById('len').value)||512));
    document.getElementById('page').textContent = generatePage(seed, len);
  };
  document.getElementById('generate').click();
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
boot();
