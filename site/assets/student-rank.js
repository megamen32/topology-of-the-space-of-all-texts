let model;
function buildTinyRanker(length){
  const A=model.alphabet.length;
  const next=model.alphabet.map(ch=>model.symbol_class[ch]||'OTHER');
  const states=[...new Set(['START',...Object.values(model.symbol_class)])];
  const costs={};
  let minC=1e9,maxC=0;
  for(const st of states){
    costs[st]=model.alphabet.map(ch=>{
      const c=model.symbol_class[ch]||'OTHER';
      const v=((model.transition_costs[st]&&model.transition_costs[st][c])||1500)+((model.emission_costs[c]&&model.emission_costs[c][ch])||1500);
      minC=Math.min(minC,v); maxC=Math.max(maxC,v); return v;
    });
  }
  const memo=new Map();
  function key(pos,st,e){return pos+'|'+st+'|'+e}
  function countExact(pos,st,e){
    if(e<0) return 0n;
    if(pos===length) return e===0?1n:0n;
    const left=length-pos;
    if(e<left*minC||e>left*maxC) return 0n;
    const k=key(pos,st,e); if(memo.has(k)) return memo.get(k);
    let total=0n; const row=costs[st];
    for(let i=0;i<A;i++) total += countExact(pos+1,next[i],e-row[i]);
    memo.set(k,total); return total;
  }
  function countBelow(E){let t=0n; for(let e=length*minC;e<E;e++) t+=countExact(0,'START',e); return t;}
  function pageIds(text){const n=normalizeText(model,text).text; const s=(n+' '.repeat(length)).slice(0,length); return [...s].map(ch=>model.index.get(ch)||0);}
  function pageCost(ids){let st='START',e=0; for(const id of ids){e+=costs[st][id]; st=next[id];} return e;}
  function rank(text){const ids=pageIds(text); const E=pageCost(ids); let r=countBelow(E); let st='START',rem=E; for(let pos=0;pos<length;pos++){for(let s=0;s<ids[pos];s++){r+=countExact(pos+1,next[s],rem-costs[st][s]);} rem-=costs[st][ids[pos]]; st=next[ids[pos]];} return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join('')};}
  function unrank(r0){let r=BigInt(r0); let E=length*minC; while(countBelow(E+1)<=r) E++; let offset=r-countBelow(E); let st='START',rem=E,ids=[]; for(let pos=0;pos<length;pos++){for(let s=0;s<A;s++){const cnt=countExact(pos+1,next[s],rem-costs[st][s]); if(offset>=cnt) offset-=cnt; else{ids.push(s); rem-=costs[st][s]; st=next[s]; break;}}} return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join('')};}
  return {rank,unrank,stats:{length,minC,maxC,spaceSize:(256n**BigInt(length)).toString()}};
}
async function boot(){model=await loadCore();document.getElementById('rankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);const x=r.rank(document.getElementById('text').value);document.getElementById('addr').value=x.rank;document.getElementById('out').textContent=show({stats:r.stats,...x});};document.getElementById('unrankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);document.getElementById('out').textContent=show({stats:r.stats,...r.unrank(document.getElementById('addr').value||'0')});};document.getElementById('rankBtn').click();}
boot();
