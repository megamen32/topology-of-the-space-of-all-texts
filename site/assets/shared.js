const PAGE_LEN = 4096;
function fmt(n){return Number(n).toLocaleString('ru-RU')}
function pct(n,total){return (100*Number(n)/Math.max(1,Number(total))).toFixed(4)+'%'}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function labelChar(ch){ if(ch===' ') return '␠'; if(ch==='\n') return '↵'; return ch; }
function codeInfo(ch){ return [...ch].map(c=>'U+'+c.codePointAt(0).toString(16).toUpperCase().padStart(4,'0')).join(' '); }
function mulberry32(seed){ let t=seed>>>0; return function(){ t+=0x6D2B79F5; let r=Math.imul(t^t>>>15,1|t); r^=r+Math.imul(r^r>>>7,61|r); return ((r^r>>>14)>>>0)/4294967296; }; }
function hashSeed(s){ let h=2166136261; for(const ch of String(s)){h^=ch.codePointAt(0); h=Math.imul(h,16777619);} return h>>>0; }
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
function weightedChoice(counter,rng,temp=0.75,filter=null){let entries=Object.entries(counter||{});if(filter)entries=entries.filter(filter);if(!entries.length)entries=Object.entries(counter||{});if(!entries.length)return null;const weights=entries.map(([k,v])=>[k,Math.pow(Number(v),temp)]);let total=weights.reduce((a,[,w])=>a+w,0);let x=rng()*total;for(const [k,w] of weights){x-=w;if(x<=0)return k;}return weights[weights.length-1][0];}
function weightedArray(rows,rng,temp=0.75){if(!rows||!rows.length)return null;let weights=rows.map(r=>Math.pow(Number(r.count||r[1]||1),temp));let total=weights.reduce((a,b)=>a+b,0);let x=rng()*total;for(let i=0;i<rows.length;i++){x-=weights[i];if(x<=0)return rows[i];}return rows[rows.length-1];}
async function loadCore(){const model=await fetch('data/model.json?ts='+Date.now()).then(r=>r.json());model.index=new Map(model.alphabet.map((ch,i)=>[ch,i]));return model;}
function normalizeText(model,s){let out='',unknown=0;for(const raw of String(s)){const ch=normChar(raw);if(!ch)continue;if(model.index.has(ch))out+=ch;else{out+=' ';unknown++;}}return {text:out,unknown};}
function cls(model,ch){return model.symbol_class[ch]||'OTHER'}
function scoreText(model,input){const {text,unknown}=normalizeText(model,input);let energy=0,prev='START',last='',rep=0,spaceRun=0;for(const ch of text){const c=cls(model,ch);energy+=(model.transition_costs[prev]&&model.transition_costs[prev][c])||1500;energy+=(model.emission_costs[c]&&model.emission_costs[c][ch])||1500;rep=ch===last?rep+1:0;last=ch;spaceRun=ch===' '?spaceRun+1:0;if(rep>4)energy+=220*(rep-3);if(spaceRun>1)energy+=600*spaceRun;prev=c;}return {normalized:text,length:text.length,unknown,energy,energyPerSymbol:energy/Math.max(1,text.length)};}
function pageFromText(model,input){const {text}=normalizeText(model,input);return (text+' '.repeat(PAGE_LEN)).slice(0,PAGE_LEN)}
function rankText(model,input){const page=pageFromText(model,input);let n=0n;for(const ch of page){n=(n<<8n)|BigInt(model.index.get(ch)??0);}return {rank:n,page};}
function unrank(model,value){let s=String(value).trim()||'0';let n=s.startsWith('0x')||s.startsWith('0X')?BigInt(s):BigInt(s);const arr=new Array(PAGE_LEN);for(let i=PAGE_LEN-1;i>=0;i--){arr[i]=model.alphabet[Number(n&255n)]||' ';n>>=8n;}return arr.join('');}
function show(obj){return JSON.stringify(obj,(k,v)=>typeof v==='bigint'?v.toString():v,2)}
