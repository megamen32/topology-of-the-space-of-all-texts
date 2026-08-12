let pages=[];
let index=0;
function compactCount(value){const text=String(value);return text.length>24?`${text.slice(0,12)}…${text.slice(-6)} (${text.length} цифр)`:text;}

async function api(path,payload){
  const response=await fetch(path,{method:payload?'POST':'GET',headers:payload?{'Content-Type':'application/json'}:undefined,body:payload?JSON.stringify(payload):undefined});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error||`API ${response.status}`);
  return data;
}
function current(){return pages[index];}
function pageFromHash(){const match=location.hash.match(/(?:^#|&)page=(\d+)/);return match?Number(match[1]):0;}
function writeHash(){history.replaceState(null,'',`#page=${index+1}`);}
function setIndex(next){index=(next+pages.length)%pages.length;writeHash();showPage();}
function showPage(){
  const page=current();
  document.getElementById('walkTitle').textContent=page.title;
  document.getElementById('walkPosition').textContent=`страница ${index+1} из ${pages.length} · 64 символа с padding · ссылка сохраняет эту точку`;
  document.getElementById('walkEnergy').textContent=page.energy;
  document.getElementById('walkNovelty').textContent=`новизна: ${Math.round(page.word_novelty_from_previous*100)}%`;
  document.getElementById('walkText').textContent=page.text;
  document.getElementById('walkAddress').textContent=page.rank_hex;
  document.getElementById('exactNeighbor').textContent='Выбери exact −1 или exact +1, чтобы открыть соседнее число.';
}
async function showNeighbor(delta){
  const page=current();
  const result=await api('/api/exact-neighbor',{length:64,rank:page.rank_hex,delta});
  document.getElementById('exactNeighbor').textContent=JSON.stringify({
    delta,
    rankHex:result.rank_hex,
    energy:result.energy,
    page:result.page,
  },null,2);
}
async function boot(){
  const [data,proof]=await Promise.all([api('/api/russian-walk'),api('/api/counting-proof')]);
  pages=data.pages;
  document.getElementById('proofScale').textContent=`Точно посчитано пространство 256^${proof.length} = 2^${proof.length*8}: ${compactCount(proof.counted_pages)} страниц; ${proof.energy_buckets} energy-бакетов. Интерактивный cluster-energy exact работает до ${proof.interactive_exact_max_length} символов. Hierarchical exact собирает ${proof.hierarchical_blocks} взаимно однозначных блоков и покрывает все 256^${proof.hierarchical_exact_max_length} страниц длиной ${proof.hierarchical_exact_max_length} без повторов.`;
  index=Math.min(Math.max(pageFromHash()-1,0),pages.length-1);
  showPage();
  writeHash();
  document.getElementById('walkPrev').onclick=()=>setIndex(index-1);
  document.getElementById('walkNext').onclick=()=>setIndex(index+1);
  document.getElementById('exactPrev').onclick=()=>showNeighbor(-1).catch(e=>{document.getElementById('exactNeighbor').textContent=String(e);});
  document.getElementById('exactNext').onclick=()=>showNeighbor(1).catch(e=>{document.getElementById('exactNeighbor').textContent=String(e);});
  document.getElementById('copyWalkAddress').onclick=()=>navigator.clipboard.writeText(current().rank_hex);
  addEventListener('keydown',(event)=>{
    if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey) return;
    if(event.target && /^(INPUT|TEXTAREA|SELECT|BUTTON)$/i.test(event.target.tagName)) return;
    if(event.key==='ArrowLeft'){event.preventDefault();setIndex(index-1);}
    if(event.key==='ArrowRight'){event.preventDefault();setIndex(index+1);}
  });
  addEventListener('hashchange',()=>{const next=Math.min(Math.max(pageFromHash()-1,0),pages.length-1);if(next!==index){index=next;showPage();}});
}
boot().catch(e=>{document.getElementById('walkText').textContent=String(e);});
