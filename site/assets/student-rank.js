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
function rngFromSeed(seed){return mulberry32(hashSeed(seed));}
function pickObj(counter,rng,temp=0.75){return weightedChoice(counter,rng,temp);}
function pickArray(rows,rng,temp=0.75){return weightedArray(rows,rng,temp);}
function realizeAbstract(tok,rng){
  const list=(wordStudent?.abstract_emissions&&wordStudent.abstract_emissions[tok])||null;
  if(!list||!list.length)return tok.replace(/[<>]/g,'');
  return list[Math.floor(rng()*list.length)]||'';
}
function isPunct(tok){return /^[.,!?;:)]$/.test(tok)}
function detok(tokens){let s='';for(const tok of tokens){if(!tok||tok==='</s>')continue;if(!s)s=tok;else if(isPunct(tok))s+=tok;else s+=' '+tok;}return s;}
function generateFSM(seed,length){
  const rng=rngFromSeed(seed);let out='',prev='START',last='',rep=0;
  for(let i=0;i<length;i++){let trans=model.transitions[prev]||model.transitions.START;let c=pickObj(trans,rng,0.58)||'SPACE';let em=model.emissions[c]||{' ':1};let ch=pickObj(em,rng,0.70,([k])=>!(rep>3&&k===last))||' ';out+=ch;rep=ch===last?rep+1:0;last=ch;prev=c;}
  return out;
}
function generateSentenceFromTemplate(template,rng){
  const types=template.split(/\s+/).filter(Boolean);let prev='<s>',toks=[];
  for(const type of types){let trans=wordStudent?.transitions?.[prev]||wordStudent?.transitions?.['<s>']||{};let tok=weightedChoice(trans,rng,0.62,([k])=>{if(k==='</s>')return type==='T';if(type==='R')return k==='<ru>'||/^[а-яё]+$/.test(k);if(type==='L')return k==='<en>'||/^[a-z]+$/.test(k);if(type==='E')return k==='<emoji>'||/\p{Emoji}/u.test(k);if(type==='N')return k==='<num>'||/^[0-9]+$/.test(k);if(type==='T')return ['.','!','?','</s>'].includes(k);if(type==='P')return [',',';',':'].includes(k);return true;});if(!tok||tok==='</s>')tok=type==='T'?(rng()<0.55?'.':rng()<0.8?'!':'?'):'<ru>';tok=realizeAbstract(tok,rng);toks.push(tok);prev=tok;}
  let s=detok(toks).replace(/\s+([.,!?;:])/g,'$1');if(!/[.!?…]$/.test(s))s+=rng()<0.55?'.':rng()<0.8?'!':'?';return s;
}
function generateSentenceStudent(seed,length){
  const rng=rngFromSeed(seed);let out=[],chars=0;const templates=sentenceStudent?.templates||[];
  while(chars<length){const row=pickArray(templates,rng,0.72);const tpl=row?row.template:'R R R T';const s=generateSentenceFromTemplate(tpl,rng);out.push(s);chars+=s.length+1;if(out.length%(2+Math.floor(rng()*4))===0){out.push('\n');chars++;}if(out.length>240)break;}
  return out.join(' ').replace(/\n\s+/g,'\n').slice(0,length);
}
function generateParagraphStudent(seed,length){
  const rng=rngFromSeed(seed);let out=[],chars=0;const shapes=paragraphStudent?.top_paragraph_shapes||[];
  while(chars<length){const row=pickArray(shapes,rng,0.72);const shape=(row?.shape||'R R R T').split(' | ').slice(0,8);let para=[];for(const tpl of shape){para.push(generateSentenceFromTemplate(tpl,rng));}const p=para.join(' ');out.push(p);chars+=p.length+2;if(out.length>80)break;}
  return out.join('\n\n').slice(0,length);
}
function setupGenerator(){
  document.getElementById('generateStudent').onclick=()=>{const seed=document.getElementById('genSeed').value;const len=Math.max(64,Math.min(4096,Number(document.getElementById('genLen').value)||512));const m=document.getElementById('genModel').value;let text=m==='fsm'?generateFSM(seed,len):m==='paragraph'?generateParagraphStudent(seed,len):generateSentenceStudent(seed,len);document.getElementById('studentGenerated').value=text;};
  document.getElementById('scoreStudentGen').onclick=()=>{document.getElementById('hierOut').textContent=show(scoreText(model,document.getElementById('studentGenerated').value));};
}
async function boot(){
  model=await loadCore();
  [wordStudent,sentenceStudent,paragraphStudent]=await Promise.all([
    fetch('data/word_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/sentence_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/paragraph_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
  ]);
  renderCards(); setupGenerator();
  document.getElementById('rankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);const x=r.rank(document.getElementById('text').value);document.getElementById('addr').value=x.rank;document.getElementById('out').textContent=show({stats:r.stats,...x});};
  document.getElementById('unrankBtn').onclick=()=>{const r=buildTinyRanker(Number(document.getElementById('len').value)||8);document.getElementById('out').textContent=show({stats:r.stats,...r.unrank(document.getElementById('addr').value||'0')});};
  document.getElementById('previewWord').onclick=()=>document.getElementById('hierOut').textContent=show(preview('word'));
  document.getElementById('previewSentence').onclick=()=>document.getElementById('hierOut').textContent=show(preview('sentence'));
  document.getElementById('previewParagraph').onclick=()=>document.getElementById('hierOut').textContent=show(preview('paragraph'));
  document.getElementById('rankBtn').click(); document.getElementById('generateStudent').click(); document.getElementById('previewSentence').click();
}
boot();
