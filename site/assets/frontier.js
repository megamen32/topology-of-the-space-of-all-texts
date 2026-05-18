function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function card(x,type){return `<article class="frontierCard"><div class="frontierMeta"><span>#${x.rank}</span><span>E=${x.energy}</span><span>${type}</span></div><p>${esc(x.text||'')}</p><details><summary>structure</summary><pre>${esc(x.shape||x.template||'')}</pre></details></article>`;}
async function tryFetch(paths){for(const p of paths){try{const r=await fetch(p+'?ts='+Date.now());if(r.ok)return await r.json();}catch(e){}}return null;}
async function boot(){
 const data=await tryFetch(['data/frontier_b2.json','../models/astar_sentence_frontier_v1/frontier_both_top20_seed7.json']);
 if(!data){document.getElementById('status').textContent='missing';return;}
 document.getElementById('status').textContent='loaded';
 const ps=data.paragraphs||[], ss=data.sentences||[];
 document.getElementById('count').textContent=ps.length+ss.length;
 document.getElementById('paragraphs').innerHTML=ps.map(x=>card(x,'paragraph')).join('')||'<p>No paragraph results yet.</p>';
 document.getElementById('sentences').innerHTML=ss.map(x=>card(x,'sentence')).join('')||'<p>No sentence results yet.</p>';
}
boot();
