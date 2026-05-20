let model, wordModel, sentenceModel, paragraphModel, clusterModel, clusterModelV2;

function rngFromSeed(seed){return mulberry32(hashSeed(seed));}
function isPunct(tok){return /^[.,!?;:)]$/.test(tok)}
function detok(tokens){let s='';for(const tok of tokens){if(!tok||tok==='</s>')continue;if(!s)s=tok;else if(isPunct(tok))s+=tok;else s+=' '+tok;}return s;}
function realizeAbstract(tok,rng){
  const list=(wordModel?.abstract_emissions&&wordModel.abstract_emissions[tok])||null;
  if(!list||!list.length)return tok.replace(/[<>]/g,'');
  return list[Math.floor(rng()*list.length)]||'';
}
function generateFSM(seed,length){
  const rng=rngFromSeed(seed); let out='', prev='START', last='', rep=0, spaceRun=0, emojiRun=0;
  for(let i=0;i<length;i++){
    let trans=model.transitions[prev]||model.transitions.START;
    let nextCls=weightedChoice(trans,rng,0.58,([k])=>!(prev==='SPACE'&&k==='SPACE')&&!(emojiRun>3&&k==='EMOJI'))||'SPACE';
    let em=model.emissions[nextCls]||{' ':1};
    let ch=weightedChoice(em,rng,0.70,([k])=>!(rep>3&&k===last))||' ';
    if(ch===' '&&spaceRun>0){nextCls=rng()<0.55?'RU':'EN';em=model.emissions[nextCls]||em;ch=weightedChoice(em,rng,0.78)||' ';}
    out+=ch; rep=ch===last?rep+1:0; last=ch; spaceRun=ch===' '?spaceRun+1:0; emojiRun=nextCls==='EMOJI'?emojiRun+1:0; prev=nextCls;
  }
  return out;
}
function generateWord(seed,length){
  const rng=rngFromSeed(seed); let toks=[], prev='<s>', chars=0;
  while(chars<length && toks.length<1000){
    const trans=wordModel?.transitions?.[prev]||wordModel?.transitions?.['<s>']||{};
    let tok=weightedChoice(trans,rng,0.68,([k])=>k!=='</s>')||'<ru>';
    tok=realizeAbstract(tok,rng);
    toks.push(tok); chars+=tok.length+1; prev=tok;
    if(toks.length%18===0){toks.push(rng()<0.5?'.':'!'); prev='<s>'; chars+=2;}
  }
  return detok(toks).slice(0,length);
}
function generateSentenceFromTemplate(template,rng){
  const types=template.split(/\s+/).filter(Boolean); let prev='<s>', toks=[];
  for(const type of types){
    let trans=wordModel?.transitions?.[prev]||wordModel?.transitions?.['<s>']||{};
    let tok=weightedChoice(trans,rng,0.62,([k])=>{
      if(k==='</s>')return type==='T';
      if(type==='R')return k==='<ru>'||/^[а-яё]+$/.test(k);
      if(type==='L')return k==='<en>'||/^[a-z]+$/.test(k);
      if(type==='E')return k==='<emoji>'||/\p{Emoji}/u.test(k);
      if(type==='N')return k==='<num>'||/^[0-9]+$/.test(k);
      if(type==='T')return ['.','!','?','</s>'].includes(k);
      if(type==='P')return [',',';',':'].includes(k);
      return true;
    });
    if(!tok||tok==='</s>')tok=type==='T'?(rng()<0.55?'.':rng()<0.8?'!':'?'):'<ru>';
    tok=realizeAbstract(tok,rng); toks.push(tok); prev=tok;
  }
  let s=detok(toks).replace(/\s+([.,!?;:])/g,'$1');
  if(!/[.!?…]$/.test(s))s+=rng()<0.55?'.':rng()<0.8?'!':'?';
  return s;
}
function generateSentence(seed,length){
  const rng=rngFromSeed(seed); let out=[], chars=0; const templates=sentenceModel?.templates||[];
  while(chars<length){
    const row=weightedArray(templates,rng,0.72); const tpl=row?row.template:'R R R T';
    const s=generateSentenceFromTemplate(tpl,rng); out.push(s); chars+=s.length+1;
    if(out.length%(2+Math.floor(rng()*4))===0){out.push('\n'); chars++;}
    if(out.length>240)break;
  }
  return out.join(' ').replace(/\n\s+/g,'\n').slice(0,length);
}

function generateCluster(seed,length){
  const rng=rngFromSeed(seed);
  if(!clusterModel) return 'cluster model is not loaded yet';
  const map=clusterModel.mapping||{};
  const byCluster={};
  for(const [tok,cl] of Object.entries(map)){(byCluster[cl]||(byCluster[cl]=[])).push(tok);}
  const trans=clusterModel.cluster_transitions||{};
  let cl=String(Math.floor(rng()*Number(clusterModel.clusters||64)));
  let out=[];
  while(out.join(' ').length<length && out.length<1000){
    const arr=byCluster[cl]||byCluster['0']||Object.keys(map).slice(0,100);
    let tok=arr[Math.floor(rng()*arr.length)]||'';
    out.push(tok);
    const row=trans[cl]||trans['0']||{};
    cl=weightedChoice(row,rng,0.72)||String(Math.floor(rng()*Number(clusterModel.clusters||64)));
    if(out.length%18===0) out.push(rng()<0.55?'.':rng()<0.75?'!':'?');
  }
  return detok(out).slice(0,length);
}

function generateParagraph(seed,length){
  const rng=rngFromSeed(seed); let out=[], chars=0; const shapes=paragraphModel?.top_paragraph_shapes||[];
  while(chars<length){
    const row=weightedArray(shapes,rng,0.70); const shape=(row?.shape||'R R R T').split(' | ').slice(0,8);
    const para=shape.map(tpl=>generateSentenceFromTemplate(tpl,rng)).join(' ');
    out.push(para); chars+=para.length+2;
    if(out.length>80)break;
  }
  return out.join('\n\n').slice(0,length);
}
async function boot(){
  model=await loadCore();
  [wordModel,sentenceModel,paragraphModel,clusterModel,clusterModelV2]=await Promise.all([
    fetch('data/word_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/sentence_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/paragraph_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/cluster_student.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
    fetch('data/cluster_student_v2.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null),
  ]);
  document.getElementById('generate').onclick=()=>{
    const seed=document.getElementById('seed').value;
    const len=Math.max(32,Math.min(4096,Number(document.getElementById('len').value)||512));
    const mode=document.getElementById('mode').value;
    const text=mode==='fsm'?generateFSM(seed,len):mode==='word'?generateWord(seed,len):mode==='cluster'?generateCluster(seed,len):mode==='clusterv2'?generateClusterV2(seed,len):mode==='paragraph'?generateParagraph(seed,len):generateSentence(seed,len);
    document.getElementById('page').value=text;
  };
  document.getElementById('scoreGenerated').onclick=()=>{document.getElementById('result').textContent=show(scoreText(model,document.getElementById('page').value));};
  document.getElementById('generate').click();
}
boot();

function generateClusterV2(seed,length){const old=clusterModel;clusterModel=clusterModelV2||old;const x=generateCluster(seed,length);clusterModel=old;return x;}
