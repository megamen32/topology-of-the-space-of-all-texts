function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function cfgName(row){const c=row.cfg||{};return [c.model, c.temp!==undefined?'t='+c.temp:'', c.branch?'b='+c.branch:''].filter(Boolean).join(' ')}
async function boot(){
 let data=null; try{data=await fetch('data/eval_leaderboard_v2.json?ts='+Date.now()).then(r=>r.json())}catch(e){}
 const rows=(data&&data.leaderboard)||[];
 document.getElementById('cfgCount').textContent=rows.length;
 if(!rows.length){document.getElementById('table').innerHTML='<p>No leaderboard yet. Eval may still be running.</p>';return;}
 const best=rows[0]; document.getElementById('bestModel').textContent=best.cfg.model; document.getElementById('bestScore').textContent=best.metrics.final_score;
 document.getElementById('table').innerHTML='<div class="rankRows">'+rows.map((r,i)=>`<div class="rankRow" data-i="${i}"><b>#${i+1}</b><span>${esc(cfgName(r))}</span><span>score ${r.metrics.final_score}</span><span>uniq ${r.metrics.unique_token_ratio}</span><span>run ${r.metrics.max_run_mean}</span></div>`).join('')+'</div>';
 function show(i){const r=rows[i]||rows[0];document.getElementById('samples').innerHTML=(r.samples||[]).slice(0,8).map((s,j)=>`<article class="frontierCard"><div class="frontierMeta"><span>${esc(cfgName(r))}</span><span>#${j}</span><span>score ${r.metrics.final_score}</span></div><p>${esc(s)}</p></article>`).join('');}
 document.querySelectorAll('.rankRow').forEach(el=>el.onclick=()=>show(Number(el.dataset.i))); show(0);
}
boot();
