function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function cfgName(row){const c=row.cfg||{};return [c.model, c.temp!==undefined?'t='+c.temp:'', c.branch?'b='+c.branch:''].filter(Boolean).join(' ')}
function metricCards(r){
 const m=r.metrics||{};
 const items=[['score',m.final_score],['distribution',m.distribution_penalty],['collapse',m.collapse_penalty],['unique',m.unique_token_ratio],['max run',m.max_run_mean],['sent len',m.sentence_len_mean],['emoji',m.emoji_rate],['punct',m.punct_rate]];
 return '<div class="metricGrid">'+items.map(([k,v])=>`<div class="metric"><div class="metricK">${esc(k)}</div><div class="metricV">${esc(v??'')}</div></div>`).join('')+'</div>';
}
async function boot(){
 let data=null; try{data=await fetch('data/eval_leaderboard_v2.json?ts='+Date.now()).then(r=>r.json())}catch(e){}
 const rows=(data&&data.leaderboard)||[];
 document.getElementById('cfgCount').textContent=rows.length;
 if(!rows.length){document.getElementById('table').innerHTML='<p>No leaderboard yet. Eval may still be running.</p>';return;}
 const best=rows[0]; document.getElementById('bestModel').textContent=best.cfg.model; document.getElementById('bestScore').textContent=best.metrics.final_score;
 document.getElementById('table').innerHTML='<div class="rankRows">'+rows.map((r,i)=>`<div class="rankRow" data-i="${i}"><b>#${i+1}</b><span>${esc(cfgName(r))}</span><span>score ${esc(r.metrics.final_score)}</span><span>uniq ${esc(r.metrics.unique_token_ratio)}</span><span>run ${esc(r.metrics.max_run_mean)}</span></div>`).join('')+'</div>';
 function show(i){
   const r=rows[i]||rows[0];
   document.querySelectorAll('.rankRow').forEach(x=>x.classList.toggle('selected', Number(x.dataset.i)===i));
   document.getElementById('samples').innerHTML=`<article class="frontierCard wide"><div class="frontierMeta"><span>${esc(cfgName(r))}</span><span>rank #${i+1}</span><span>score ${esc(r.metrics.final_score)}</span></div>${metricCards(r)}</article>`+(r.samples||[]).slice(0,12).map((s,j)=>`<article class="frontierCard"><div class="frontierMeta"><span>${esc(cfgName(r))}</span><span>sample #${j+1}</span></div><p>${esc(s)}</p></article>`).join('');
 }
 document.querySelectorAll('.rankRow').forEach(el=>el.onclick=()=>show(Number(el.dataset.i))); show(0);
}
boot();
