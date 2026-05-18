async function bootProof(){
  let i=0; const ids=['flowText','flowDigits','flowNumber','flowAddress'];
  setInterval(()=>{ids.forEach(id=>document.getElementById(id)?.classList.remove('active'));document.getElementById(ids[i%ids.length])?.classList.add('active');i++;},900);
  const model=await loadCore();
  document.getElementById('proveBtn').onclick=()=>{
    const q=document.getElementById('query').value;
    const page=pageFromText(model,q);
    let n=0n;
    for(const ch of page){n=(n<<8n)|BigInt(model.index.get(ch)??0);}
    const digits=[...page.slice(0,24)].map(ch=>model.index.get(ch)??0);
    document.getElementById('proofOut').textContent=show({
      input:q,
      normalizedPagePrefix:page.slice(0,80),
      firstBase256Digits:digits,
      addressBase64url:encodeB64u(n),
      checkPrefix: numberToPage(n).slice(0,80),
      statement:'unrank(rank(page)) restores the same 4096-symbol page'
    });
  };
  document.getElementById('proveBtn').click();
}
bootProof();
