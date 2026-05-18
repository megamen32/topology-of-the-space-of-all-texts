function fmt(n){return Number(n).toLocaleString('ru-RU')}
function pct(n,total){return (100*Number(n)/Math.max(1,Number(total))).toFixed(4)+'%'}
function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function labelChar(ch){ if(ch===' ') return '␠'; if(ch==='\n') return '↵'; return ch; }
function codeInfo(ch){ return [...ch].map(c=>'U+'+c.codePointAt(0).toString(16).toUpperCase().padStart(4,'0')).join(' '); }
function renderSummary(s){
  const items=[['Characters',s.chars_total],['Unique chars',s.chars_unique],['Tokens',s.words_total],['Unique tokens',s.words_unique],['Sentences',s.sentences],['Paragraphs',s.paragraphs]];
  document.getElementById('summary').innerHTML=items.map(([k,v])=>`<div><h2>${k}</h2><div class="stat"><span>${fmt(v)}</span><small>${k}</small></div></div>`).join('');
}
function renderBars(id, rows, total, formatter){
  const max=Math.max(...rows.map(r=>Array.isArray(r[0])?r[1]:r[1]),1);
  document.getElementById(id).innerHTML=rows.map((r,i)=>{
    let key=r[0], val=r[1];
    if(Array.isArray(key)) key=key.join(' → ');
    const w=100*val/max;
    return `<div class="barRow"><div class="barLabel"><b>${i+1}</b> ${esc(formatter?formatter(key):key)}</div><div class="barTrack"><div class="bar" style="width:${w}%"></div></div><div class="barVal">${fmt(val)} · ${pct(val,total)}</div></div>`;
  }).join('');
}
async function boot(){
  const data=await fetch('data/analytics.json?ts='+Date.now()).then(r=>r.json());
  renderSummary(data.summary);
  const total=data.summary.chars_total;
  document.getElementById('charGrid').innerHTML=data.top_chars.map(([ch,n],i)=>`<span data-i="${i}" title="${fmt(n)}">${esc(labelChar(ch))}</span>`).join('');
  [...document.querySelectorAll('#charGrid span')].forEach(el=>{
    el.onclick=()=>{
      const i=Number(el.dataset.i); const [ch,n]=data.top_chars[i];
      document.getElementById('charInfo').textContent=JSON.stringify({rank:i+1,char:ch,label:labelChar(ch),code:codeInfo(ch),count:n,share:pct(n,total)},null,2);
    };
  });
  document.querySelector('#charGrid span')?.click();
  renderBars('wordChart', data.top_words.slice(0,60), data.summary.words_total);
  renderBars('starterChart', data.top_starters.slice(0,50), data.summary.sentences);
  renderBars('endingChart', data.top_endings.slice(0,50), data.summary.sentences);
  renderBars('bigramChart', data.top_word_bigrams.slice(0,80), data.summary.words_total);
}
boot();
