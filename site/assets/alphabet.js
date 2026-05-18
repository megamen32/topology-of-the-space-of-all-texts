async function boot(){
  const model=await loadCore(); const stats=await fetch('data/analytics.json?ts='+Date.now()).then(r=>r.json()).catch(()=>null);
  document.getElementById('coverage').textContent=(model.coverage*100).toFixed(4)+'%';
  document.getElementById('unique').textContent=fmt(model.unique_chars); document.getElementById('total').textContent=fmt(model.total_chars);
  const freq=new Map((stats?.top_chars||[]).map((x,i)=>[x[0],{rank:i+1,count:x[1]}]));
  document.getElementById('alphabet').innerHTML=model.alphabet.map(ch=>`<span data-ch="${escapeHtml(ch)}">${escapeHtml(labelChar(ch))}</span>`).join('');
  document.querySelectorAll('#alphabet span').forEach((el,i)=>{el.onclick=()=>{const ch=model.alphabet[i];const f=freq.get(ch)||{};document.getElementById('charInfo').textContent=show({alphabetIndex:i,char:ch,label:labelChar(ch),code:codeInfo(ch),frequencyRank:f.rank??null,count:f.count??0,share:f.count?pct(f.count,model.total_chars):'0%'});};});
  document.querySelector('#alphabet span')?.click();
  document.getElementById('emoji').innerHTML=model.emoji_top.slice(0,50).map(([ch,n])=>`<span title="${fmt(n)}">${escapeHtml(ch)}</span>`).join('');
}
boot();
