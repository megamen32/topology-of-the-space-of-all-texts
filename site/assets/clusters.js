function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
let data=null;
function summarizeFromMapping(model){
  const by={};
  for(const [tok,cl] of Object.entries(model.mapping||{})){(by[cl]||(by[cl]=[])).push(tok)}
  return Object.entries(by).map(([id,toks])=>({id:Number(id),size:toks.length,top:toks.slice(0,50)})).sort((a,b)=>a.id-b.id)
}
function topTransitions(id){
  const row=(data.cluster_transitions||{})[String(id)]||{};
  return Object.entries(row).sort((a,b)=>b[1]-a[1]).slice(0,12).map(([k,v])=>`C${k}:${v}`).join(' · ');
}
function render(){
  const q=(document.getElementById('search').value||'').toLowerCase().trim();
  const clusters=(data.cluster_summaries&&data.cluster_summaries.length?data.cluster_summaries:summarizeFromMapping(data));
  document.getElementById('clusterCount').textContent=data.clusters||clusters.length;
  document.getElementById('vocabCount').textContent=data.vocab||Object.keys(data.mapping||{}).length;
  const filtered=clusters.filter(c=>!q||String(c.id)===q||c.top.some(t=>String(t).toLowerCase().includes(q)));
  document.getElementById('clusters').innerHTML=filtered.map(c=>`<article class="clusterCard" data-id="${c.id}"><div class="frontierMeta"><span>C${c.id}</span><span>${c.size} tokens</span></div><p>${c.top.slice(0,28).map(esc).join(' ')}</p><small>${esc(topTransitions(c.id))}</small></article>`).join('') || '<p>No clusters found.</p>';
  document.querySelectorAll('.clusterCard').forEach(el=>el.onclick=()=>showCluster(Number(el.dataset.id)));
  if(filtered[0]) showCluster(filtered[0].id);
}
function showCluster(id){
  const clusters=(data.cluster_summaries&&data.cluster_summaries.length?data.cluster_summaries:summarizeFromMapping(data));
  const c=clusters.find(x=>Number(x.id)===Number(id)); if(!c)return;
  const row=(data.cluster_transitions||{})[String(id)]||{};
  const trans=Object.entries(row).sort((a,b)=>b[1]-a[1]).slice(0,30);
  document.getElementById('details').innerHTML=`<div class="metricGrid"><div class="metric"><div class="metricK">cluster</div><div class="metricV">C${c.id}</div></div><div class="metric"><div class="metricK">size</div><div class="metricV">${c.size}</div></div><div class="metric"><div class="metricK">top tokens</div><div class="metricV">${esc(c.top.join(' '))}</div></div><div class="metric"><div class="metricK">top transitions</div><div class="metricV">${esc(trans.map(([k,v])=>`C${k}=${v}`).join('\n'))}</div></div></div>`;
}
async function load(){
 data=null;
 const mode=document.getElementById('modelSelect').value;
 const paths=mode==='v2'?['data/cluster_student_v2.json','data/cluster_student.json']:['data/cluster_student.json'];
 for(const p of paths){try{const r=await fetch(p+'?ts='+Date.now());if(r.ok){data=await r.json();break}}catch(e){}}
 if(!data){document.getElementById('clusters').innerHTML='<p>No cluster model exported yet.</p>';return}
 render();
}
document.getElementById('modelSelect').onchange=load;
document.getElementById('search').oninput=render;
load();
