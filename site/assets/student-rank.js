let model, wordStudent, sentenceStudent, paragraphStudent;
function buildTinyRanker(length){
  const A=model.alphabet.length;
  const next=model.alphabet.map(ch=>model.symbol_class[ch]||'OTHER');
  const states=[...new Set(['START',...Object.values(model.symbol_class)])];
  const costs={}; let minC=1e9,maxC=0;
  for(const st of states){costs[st]=model.alphabet.map(ch=>{const c=model.symbol_class[ch]||'OTHER';const v=((model.transition_costs[st]&&model.transition_costs[st][c])||1500)+((model.emission_costs[c]&&model.emission_costs[c][ch])||1500);minC=Math.min(minC,v);maxC=Math.max(maxC,v);return v;});}
  const memo=new Map(); const key=(p,s,e)=>p+'|'+s+'|'+e;
  function countExact(pos,st,e){if(e<0)return 0n;if(pos===length)return e===0?1n:0n;const left=length-pos;if(e<left*minC||e>left*maxC)return 0n;const k=key(pos,st,e);if(memo.has(k))return memo.get(k);let total=0n;for(let i=0;i<A;i++)total+=countExact(pos+1,next[i],e-costs[st][i]);memo.set(k,total);return total;}
  function countBelow(E){let t=0n;for(let e=length*minC;e<E;e++)t+=countExact(0,'START',e);return t;}
  function pageIds(text){const n=normalizeText(model,text).text;const s=(n+' '.repeat(length)).slice(0,length);return [...s].map(ch=>model.index.get(ch)||0);}
  function pageCost(ids){let st='START',e=0;for(const id of ids){e+=costs[st][id];st=next[id];}return e;}
  function rank(text){const ids=pageIds(text);const E=pageCost(ids);let r=countBelow(E);let st='START',rem=E;for(let pos=0;pos<length;pos++){for(let s=0;s<ids[pos];s++)r+=countExact(pos+1,next[s],rem-costs[st][s]);rem-=costs[st][ids[pos]];st=next[ids[pos]];}return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join('')};}
  function unrank(r0){let r=BigInt(r0);let E=length*minC;while(countBelow(E+1)<=r)E++;let offset=r-countBelow(E);let st='START',rem=E,ids=[];for(let pos=0;pos<length;pos++){for(let s=0;s<A;s++){const cnt=countExact(pos+1,next[s],rem-costs[st][s]);if(offset>=cnt)offset-=cnt;else{ids.push(s);rem-=costs[st][s];st=next[s];break;}}}return {rank:r.toString(),energy:E,page:ids.map(i=>model.alphabet[i]).join('')};}
  return {rank,unrank,stats:{length,minC,maxC,spaceSize:(256n**BigInt(length)).toString()}};
}
function renderCards(){
  const cards=[
    {name:'class-FSM',status:'legacy baseline',size:'~16 KB',desc:'Tiny exact-countable proof model. Collapses to vowel/space attractors; not product ordering.'},
    {name:'word student',status:'active',size:wordStudent?((JSON.stringify(wordStudent).length/1024/1024).toFixed(2)+' MB'):'loading',desc:`${wordStudent?.vocab?.length||0} tokens, ${Object.keys(wordStudent?.transitions||{}).length} transition states.`},
    {name:'sentence student',status:'active',size:sentenceStudent?((JSON.stringify(sentenceStudent).length/1024/1024).toFixed(2)+' MB'):'loading',desc:`${sentenceStudent?.templates?.length||0} exported templates; sentence topology layer.`},
    {name:'paragraph student',status:'training/exported',size:paragraphStudent?((JSON.stringify(paragraphStudent).length/1024/1024).toFixed(2)+' MB'):'not ready',desc:`${paragraphStudent?.stats?.unique_shapes||0} paragraph shapes; ${paragraphStudent?.stats?.transition_states||0} transition states.`},
  ];
  document.getElementById('studentCards').innerHTML=cards.map(c=>`<div class="studentCard"><div class="studentStatus">${escapeHtml(c.status)}</div><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml(c.desc)}</p><small>${escapeHtml(c.size)}</small></div>`).join('');
}
function preview(kind){
  if(kind==='word') return {topVocab:(wordStudent?.vocab||[]).slice(0,80), sampleTransitions:Object.fromEntries(Object.entries(wordStudent?.transitions||{}).slice(0,8))};
  if(kind==='sentence') return {summary:sentenceStudent?.summary, topTemplates:(sentenceStudent?.templates||[]).slice(0,20)};
  return {stats:paragraphStudent?.stats, topShapes:(paragraphStudent?.top_paragraph_shapes||[]).slice(0,20), samples:(paragraphStudent?.samples||[]).slice(0,5)};
}
async function boot(){
  model=await loadCore();
  [wordStudent,sentenceStudent,paragraphStudent]=await Promise.all([
    fetch('data/word_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/sentence_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/paragraph_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
  ]);
  renderCards();
  document.getElementById('rankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);const x=r.rank(document.getElementById('text').value);document.getElementById('addr').value=x.rank;document.getElementById('out').textContent=show({stats:r.stats,...x});};
  document.getElementById('unrankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);document.getElementById('out').textContent=show({stats:r.stats,...r.unrank(document.getElementById('addr').value||'0')});};
  document.getElementById('previewWord').onclick=()=>document.getElementById('hierOut').textContent=show(preview('word'));
  document.getElementById('previewSentence').onclick=()=>document.getElementById('hierOut').textContent=show(preview('sentence'));
  document.getElementById('previewParagraph').onclick=()=>document.getElementById('hierOut').textContent=show(preview('paragraph'));
  document.getElementById('rankBtn').click(); document.getElementById('previewSentence').click();
}
boot();
