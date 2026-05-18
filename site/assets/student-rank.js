let model, wordStudent, sentenceStudent, paragraphStudent;
function renderInfo(el,items){
  el.innerHTML='<div class="metricGrid">'+items.map(x=>`<div class="metric"><div class="metricK">${escapeHtml(x.k)}</div><div class="metricV">${escapeHtml(String(x.v))}</div><div class="metricS">${escapeHtml(x.s||'')}</div></div>`).join('')+'</div>';
}
function buildTinyRanker(length){
  const A=model.alphabet.length, next=model.alphabet.map(ch=>model.symbol_class[ch]||'OTHER');
  const states=[...new Set(['START',...Object.values(model.symbol_class)])];
  const costs={}; let minC=1e9,maxC=0;
  for(const st of states){costs[st]=model.alphabet.map(ch=>{const c=model.symbol_class[ch]||'OTHER';const v=((model.transition_costs[st]&&model.transition_costs[st][c])||1500)+((model.emission_costs[c]&&model.emission_costs[c][ch])||1500);minC=Math.min(minC,v);maxC=Math.max(maxC,v);return v;});}
  const memo=new Map(), key=(p,s,e)=>p+'|'+s+'|'+e;
  function countExact(pos,st,e){if(e<0)return 0n;if(pos===length)return e===0?1n:0n;const left=length-pos;if(e<left*minC||e>left*maxC)return 0n;const k=key(pos,st,e);if(memo.has(k))return memo.get(k);let total=0n;for(let i=0;i<A;i++)total+=countExact(pos+1,next[i],e-costs[st][i]);memo.set(k,total);return total;}
  function countBelow(E){let t=0n;for(let e=length*minC;e<E;e++)t+=countExact(0,'START',e);return t;}
  function pageIds(text){const n=normalizeText(model,text).text;const s=(n+' '.repeat(length)).slice(0,length);return [...s].map(ch=>model.index.get(ch)||0);}
  function pageCost(ids){let st='START',e=0;for(const id of ids){e+=costs[st][id];st=next[id];}return e;}
  function rank(text){const ids=pageIds(text), E=pageCost(ids);let r=countBelow(E), st='START', rem=E;for(let pos=0;pos<length;pos++){for(let s=0;s<ids[pos];s++)r+=countExact(pos+1,next[s],rem-costs[st][s]);rem-=costs[st][ids[pos]];st=next[ids[pos]];}return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join(''), countedBeforeEnergy:countBelow(E).toString()};}
  function unrank(r0){let r=BigInt(r0), E=length*minC;while(countBelow(E+1)<=r)E++;let offset=r-countBelow(E), st='START', rem=E, ids=[];for(let pos=0;pos<length;pos++){for(let s=0;s<A;s++){const cnt=countExact(pos+1,next[s],rem-costs[st][s]);if(offset>=cnt)offset-=cnt;else{ids.push(s);rem-=costs[st][s];st=next[s];break;}}}return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join('')};}
  return {rank,unrank,stats:{length,minC,maxC,spaceSize:(256n**BigInt(length)).toString()}};
}
function renderCards(){
  const cards=[
    {name:'class-FSM',status:'legacy baseline',size:'~16 KB',desc:'Proof/counting baseline. Not product quality; collapses to simple attractors.'},
    {name:'word student',status:'active generation layer',size:wordStudent?((JSON.stringify(wordStudent).length/1024/1024).toFixed(2)+' MB'):'loading',desc:`${wordStudent?.vocab?.length||0} tokens, ${Object.keys(wordStudent?.transitions||{}).length} transition states.`},
    {name:'sentence student',status:'active generation layer',size:sentenceStudent?((JSON.stringify(sentenceStudent).length/1024/1024).toFixed(2)+' MB'):'loading',desc:`${sentenceStudent?.templates?.length||0} exported sentence templates.`},
    {name:'paragraph student',status:'next ranking candidate',size:paragraphStudent?((JSON.stringify(paragraphStudent).length/1024/1024).toFixed(2)+' MB'):'training/not exported yet',desc:`${paragraphStudent?.stats?.unique_shapes||0} paragraph shapes; ${paragraphStudent?.stats?.transition_states||0} transition states.`},
  ];
  document.getElementById('studentCards').innerHTML=cards.map(c=>`<div class="studentCard"><div class="studentStatus">${escapeHtml(c.status)}</div><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml(c.desc)}</p><small>${escapeHtml(c.size)}</small></div>`).join('');
}
function layerPreview(kind){
  if(kind==='word') return [
    {k:'vocab size',v:wordStudent?.vocab?.length||0},{k:'transition states',v:Object.keys(wordStudent?.transitions||{}).length},{k:'top words',v:(wordStudent?.vocab||[]).slice(0,24).join(' ')}
  ];
  if(kind==='sentence') return [
    {k:'exported templates',v:sentenceStudent?.templates?.length||0},{k:'sentences in corpus',v:sentenceStudent?.summary?.sentences||'?'},{k:'top template',v:sentenceStudent?.templates?.[0]?.template||'not ready'},{k:'example',v:sentenceStudent?.templates?.[0]?.samples?.[0]||''}
  ];
  return [
    {k:'unique paragraph shapes',v:paragraphStudent?.stats?.unique_shapes||0},{k:'transition states',v:paragraphStudent?.stats?.transition_states||0},{k:'top shape',v:paragraphStudent?.top_paragraph_shapes?.[0]?.shape||'not ready'},{k:'sample',v:paragraphStudent?.samples?.[0]||''}
  ];
}
async function boot(){
  model=await loadCore();
  [wordStudent,sentenceStudent,paragraphStudent]=await Promise.all([
    fetch('data/word_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/sentence_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/paragraph_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
  ]);
  renderCards();
  document.getElementById('rankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);const x=r.rank(document.getElementById('text').value);document.getElementById('addr').value=x.rank;renderInfo(document.getElementById('rankCards'),[{k:'student rank',v:x.rank},{k:'energy',v:x.energy},{k:'normalized page',v:x.page},{k:'pages cheaper',v:x.countedBeforeEnergy},{k:'space size',v:r.stats.spaceSize}]);};
  document.getElementById('unrankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);const x=r.unrank(document.getElementById('addr').value||'0');renderInfo(document.getElementById('rankCards'),[{k:'address',v:x.rank},{k:'energy bucket',v:x.energy},{k:'page',v:x.page}]);};
  document.getElementById('previewWord').onclick=()=>renderInfo(document.getElementById('hierCards'),layerPreview('word'));
  document.getElementById('previewSentence').onclick=()=>renderInfo(document.getElementById('hierCards'),layerPreview('sentence'));
  document.getElementById('previewParagraph').onclick=()=>renderInfo(document.getElementById('hierCards'),layerPreview('paragraph'));
  document.getElementById('rankBtn').click();document.getElementById('previewSentence').click();
}
boot();
