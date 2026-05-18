let model, wordModel, sentenceModel;
const PAGE_LEN = 4096;

function mulberry32(seed){ let t=seed>>>0; return function(){ t+=0x6D2B79F5; let r=Math.imul(t^t>>>15,1|t); r^=r+Math.imul(r^r>>>7,61|r); return ((r^r>>>14)>>>0)/4294967296; }; }
function hashSeed(s){ let h=2166136261; for(const ch of String(s)){h^=ch.codePointAt(0); h=Math.imul(h,16777619);} return h>>>0; }
function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function isCombining(ch){return /\p{Mark}/u.test(ch)}
function normChar(ch){
  if(['\ufeff','\u200b','\u200c','\u200d','\ufe0f','\ufe0e'].includes(ch)) return '';
  if(isCombining(ch)) return '';
  if(['\t','\r','\u00a0','\u2800'].includes(ch)) return ' ';
  if(['“','”','„','‟'].includes(ch)) return '"';
  if(['’','‘','‚','`','´'].includes(ch)) return "'";
  if(['–','—','−'].includes(ch)) return '-';
  return ch.toLowerCase();
}
function normalizeText(s){
  let out='', unknown=0;
  for(const raw of String(s)){
    const ch=normChar(raw); if(!ch) continue;
    if(model.index.has(ch)) out+=ch; else {out+=' '; unknown++;}
  }
  return {text:out, unknown};
}
function cls(ch){return model.symbol_class[ch] || 'OTHER';}
function weightedChoice(counter,rng,temp=0.75,filter=null){
  let entries=Object.entries(counter||{}); if(filter) entries=entries.filter(filter); if(!entries.length) entries=Object.entries(counter||{});
  if(!entries.length) return null;
  const weights=entries.map(([k,v])=>[k,Math.pow(Number(v),temp)]); let total=weights.reduce((a,[,w])=>a+w,0); let x=rng()*total;
  for(const [k,w] of weights){x-=w;if(x<=0)return k;} return weights[weights.length-1][0];
}
function weightedArray(rows,rng,temp=0.75){
  if(!rows || !rows.length) return null;
  const max=Math.max(...rows.map(r=>Number(r.count || r[1] || 1)),1);
  let weights=rows.map(r=>Math.pow(Number(r.count || r[1] || 1),temp));
  let total=weights.reduce((a,b)=>a+b,0); let x=rng()*total;
  for(let i=0;i<rows.length;i++){x-=weights[i]; if(x<=0) return rows[i];}
  return rows[rows.length-1];
}
function scoreText(input){
  const {text,unknown}=normalizeText(input); let energy=0, prev='START', last='', rep=0, spaceRun=0;
  for(const ch of text){
    const c=cls(ch);
    energy += (model.transition_costs[prev] && model.transition_costs[prev][c]) || 1500;
    energy += (model.emission_costs[c] && model.emission_costs[c][ch]) || 1500;
    rep = ch===last ? rep+1 : 0; last=ch;
    spaceRun = ch===' ' ? spaceRun+1 : 0;
    if(rep>4) energy += 220*(rep-3);
    if(spaceRun>1) energy += 600*spaceRun;
    prev=c;
  }
  return {normalized:text, length:text.length, unknown, energy, energyPerSymbol: energy/Math.max(1,text.length)};
}
function pageFromText(input){ const {text}=normalizeText(input); return (text + ' '.repeat(PAGE_LEN)).slice(0,PAGE_LEN); }
function rankText(input){ const page=pageFromText(input); let n=0n; for(const ch of page){ n=(n<<8n) | BigInt(model.index.get(ch) ?? 0); } return {rank:n, page}; }
function unrank(value){ let s=String(value).trim() || '0'; let n=s.startsWith('0x')||s.startsWith('0X') ? BigInt(s) : BigInt(s); const arr=new Array(PAGE_LEN); for(let i=PAGE_LEN-1;i>=0;i--){ arr[i]=model.alphabet[Number(n & 255n)] || ' '; n >>= 8n; } return arr.join(''); }

function generateFSM(seed,length){
  const rng=mulberry32(hashSeed(seed)); let out='', prev='START', last='', rep=0, spaceRun=0, emojiRun=0;
  for(let i=0;i<length;i++){
    let trans=model.transitions[prev] || model.transitions.START;
    let nextCls=weightedChoice(trans,rng,0.58,([k])=>!(prev==='SPACE'&&k==='SPACE') && !(emojiRun>3&&k==='EMOJI')) || 'SPACE';
    let em=model.emissions[nextCls] || {' ':1};
    let ch=weightedChoice(em,rng,0.70,([k])=>!(rep>3&&k===last)) || ' ';
    if(ch===' ' && spaceRun>0){ nextCls=rng()<0.55?'RU':'EN'; em=model.emissions[nextCls]||em; ch=weightedChoice(em,rng,0.78)||' '; }
    out+=ch; rep=ch===last?rep+1:0; last=ch; spaceRun=ch===' '?spaceRun+1:0; emojiRun=nextCls==='EMOJI'?emojiRun+1:0; prev=nextCls;
  }
  return out;
}
function realizeAbstract(tok,rng){
  const list=(wordModel.abstract_emissions && wordModel.abstract_emissions[tok]) || null;
  if(!list || !list.length) return tok.replace(/[<>]/g,'');
  return list[Math.floor(rng()*list.length)] || '';
}
function isPunct(tok){return /^[.,!?;:)]$/.test(tok)}
function detok(tokens){
  let s='';
  for(const tok of tokens){
    if(!tok || tok==='</s>') continue;
    if(!s) s=tok;
    else if(isPunct(tok)) s+=tok;
    else if(tok==='(') s+=' '+tok;
    else s+=' '+tok;
  }
  return s;
}
function generateSentenceFromTemplate(template,rng){
  const types=template.split(/\s+/).filter(Boolean);
  let prev='<s>', toks=[];
  for(const type of types){
    let trans=wordModel.transitions[prev] || wordModel.transitions['<s>'] || {};
    let tok=weightedChoice(trans,rng,0.62,([k])=>{
      if(k==='</s>') return type==='T';
      if(type==='R') return k==='<ru>' || /^[а-яё]+$/.test(k);
      if(type==='L') return k==='<en>' || /^[a-z]+$/.test(k);
      if(type==='E') return k==='<emoji>' || /\p{Emoji}/u.test(k);
      if(type==='N') return k==='<num>' || /^[0-9]+$/.test(k);
      if(type==='T') return ['.','!','?','</s>'].includes(k);
      if(type==='P') return [',',';',':'].includes(k);
      return true;
    });
    if(!tok || tok==='</s>') { tok = type==='T' ? (rng()<0.55?'.':rng()<0.8?'!':'?') : '<ru>'; }
    tok=realizeAbstract(tok,rng);
    toks.push(tok); prev=tok;
  }
  let s=detok(toks).replace(/\s+([.,!?;:])/g,'$1');
  if(!/[.!?…]$/.test(s)) s += rng()<0.55?'.':rng()<0.8?'!':'?';
  return s;
}
function generateSentenceStudent(seed,length){
  const rng=mulberry32(hashSeed(seed));
  const templates=sentenceModel.templates || [];
  let out=[]; let chars=0;
  while(chars < length){
    const row=weightedArray(templates,rng,0.72);
    const tpl=row ? row.template : 'R R R T';
    let s=generateSentenceFromTemplate(tpl,rng);
    // Sometimes use real sample shape for stability? no verbatim samples; only template.
    out.push(s); chars += s.length + 1;
    if(out.length % (2+Math.floor(rng()*4))===0) { out.push('\n'); chars += 1; }
    if(out.length>200) break;
  }
  return out.join(' ').replace(/\n\s+/g,'\n').slice(0,length);
}
function show(obj){return JSON.stringify(obj,(k,v)=>typeof v==='bigint'?v.toString():v,2)}
async function boot(){
  model=await fetch('data/model.json?ts='+Date.now()).then(r=>r.json()); model.index=new Map(model.alphabet.map((ch,i)=>[ch,i]));
  wordModel=await fetch('data/word_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null);
  sentenceModel=await fetch('data/sentence_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>({templates:[]}));
  document.getElementById('coverage').textContent=(model.coverage*100).toFixed(4)+'%';
  document.getElementById('classes').textContent=new Set(Object.values(model.symbol_class)).size;
  document.getElementById('alphabet').innerHTML=model.alphabet.map(ch=>`<span title="tap analytics page for frequency">${escapeHtml(ch===' '?'␠':ch==='\n'?'↵':ch)}</span>`).join('');
  document.getElementById('emoji').innerHTML=model.emoji_top.slice(0,50).map(([ch,n])=>`<span title="${n}">${escapeHtml(ch)}</span>`).join('');
  document.getElementById('generate').onclick=()=>{ const seed=document.getElementById('seed').value; const len=Math.max(32,Math.min(4096,Number(document.getElementById('len').value)||512)); const mode=document.getElementById('mode')?.value||'sentence'; const text=mode==='fsm'?generateFSM(seed,len):generateSentenceStudent(seed,len); document.getElementById('page').value=text; };
  document.getElementById('scoreGenerated').onclick=()=>{ document.getElementById('result').textContent=show(scoreText(document.getElementById('page').value)); };
  document.getElementById('scoreBtn').onclick=()=>{ document.getElementById('result').textContent=show(scoreText(document.getElementById('query').value)); };
  document.getElementById('rankBtn').onclick=()=>{ const r=rankText(document.getElementById('query').value); document.getElementById('rankInput').value='0x'+r.rank.toString(16); document.getElementById('result').textContent=show({rankHex:'0x'+r.rank.toString(16), rankDec:r.rank.toString(), normalizedPreview:r.page.slice(0,512), score:scoreText(document.getElementById('query').value)}); };
  document.getElementById('searchBtn').onclick=()=>{ const q=document.getElementById('query').value; const r=rankText(q); document.getElementById('result').textContent=show({query:q, exactPagePreview:r.page.slice(0,1024), rankHex:'0x'+r.rank.toString(16), score:scoreText(q)}); };
  document.getElementById('unrankBtn').onclick=()=>{ try{ const t=unrank(document.getElementById('rankInput').value); document.getElementById('unrankResult').textContent=t.slice(0,2048); }catch(e){ document.getElementById('unrankResult').textContent=String(e); } };
  document.getElementById('generate').click();
}
boot();
