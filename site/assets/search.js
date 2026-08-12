let model;
const API_BASE='';
function selectedMode(){return document.getElementById('rankMode').value;}
function selectedLength(){return Number(document.getElementById('rankLength').value)||8;}
function usesServerExact(){return selectedMode()!=='base256';}
async function api(path,payload){const response=await fetch(API_BASE+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error||`API ${response.status}`);return data;}
function baseRank(query){const r=rankText(model,query);return {rank:r.rank,rankHex:'0x'+r.rank.toString(16),rankDec:r.rank.toString(),page:r.page,energy:'local score only'};}
async function exactRank(query){return api('/api/rank',{mode:selectedMode(),length:selectedLength(),text:query});}
function rankAddress(result){return result.rank_hex||('0x'+BigInt(result.rank).toString(16));}
async function boot(){model=await loadCore();
  document.getElementById('rankMode').onchange=()=>{if(selectedMode()==='exact_hierarchical_v1'&&selectedLength()<256)document.getElementById('rankLength').value='4096';if(selectedMode()==='exact_cluster_mvp'&&selectedLength()>256)document.getElementById('rankLength').value='256';};
  document.getElementById('rankLength').onchange=()=>{if(selectedLength()>256)document.getElementById('rankMode').value='exact_hierarchical_v1';};
  document.getElementById('scoreBtn').onclick=()=>{document.getElementById('result').textContent=show(scoreText(model,document.getElementById('query').value));};
  document.getElementById('rankBtn').onclick=async()=>{try{const query=document.getElementById('query').value;const r=usesServerExact()?await exactRank(query):baseRank(query);document.getElementById('rankInput').value=rankAddress(r);document.getElementById('result').textContent=show({...r,mode:selectedMode(),score:scoreText(model,query)});}catch(e){document.getElementById('result').textContent=String(e);}};
  document.getElementById('searchBtn').onclick=async()=>{try{const query=document.getElementById('query').value;const r=usesServerExact()?await exactRank(query):baseRank(query);document.getElementById('rankInput').value=rankAddress(r);document.getElementById('result').textContent=show({query,mode:selectedMode(),exactPagePreview:(r.page||'').slice(0,1024),rankHex:rankAddress(r),energy:r.energy,score:scoreText(model,query)});}catch(e){document.getElementById('result').textContent=String(e);}};
  document.getElementById('unrankBtn').onclick=async()=>{try{const rank=document.getElementById('rankInput').value;const result=usesServerExact()?await api('/api/unrank',{mode:selectedMode(),length:selectedLength(),rank}):{page:unrank(model,rank)};document.getElementById('unrankResult').textContent=show(result);}catch(e){document.getElementById('unrankResult').textContent=String(e);}};
}
boot();
