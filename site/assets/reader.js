(() => {
  const byId = id => document.getElementById(id);
  const paper = byId('readingPaper');
  const lookup = byId('reverseLookup');
  const viewport = byId('leafWindow');
  const result = byId('unrankResult');
  const prev = byId('prevLeaf');
  const next = byId('nextLeaf');
  const position = byId('leafPosition');
  const flow = document.createElement('div');
  const range = document.createRange();
  flow.style.whiteSpace = 'break-spaces';
  // WebKit needs a column width to fragment overflow when column-count is one.
  if (getComputedStyle(result).columnWidth === 'auto') result.style.columnWidth = '1px';
  let runs = [];
  let length = 0;
  let bookmark = 0;

  function characterX(offset) {
    const {node, start} = runs.findLast(run => run.start <= offset);
    if (node.nodeType === Node.ELEMENT_NODE) return node.getBoundingClientRect().left;
    range.setStart(node, offset - start);
    range.setEnd(node, offset - start + 1);
    const rect = range.getBoundingClientRect();
    return rect.left + rect.width / 2;
  }

  function firstCharacter(left) {
    let low = 0;
    let high = length - 1;
    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      if (characterX(mid) < left) low = mid + 1;
      else high = mid;
    }
    return low;
  }

  function fitHeight() {
    if (lookup?.open) return;
    const box = paper.getBoundingClientRect();
    if (!box.height) return;
    const chrome = Math.round(box.bottom + window.scrollY - viewport.getBoundingClientRect().height + 14) + 'px';
    if (paper.style.getPropertyValue('--reader-chrome') !== chrome) paper.style.setProperty('--reader-chrome', chrome);
  }

  function layout(turn = 0) {
    fitHeight();
    // A block fragmented by CSS columns has one rect per occupied column.
    const fragments = flow.getClientRects();
    if (!fragments.length) return;
    const columns = Number(getComputedStyle(result).columnCount) || 1;
    const starts = Array.from(fragments).filter((_, i) => i % columns === 0);
    const x = bookmark ? characterX(bookmark) : starts[0].left;
    const current = Math.max(0, starts.findLastIndex(rect => rect.left <= x));
    const page = Math.max(0, Math.min(current + turn, starts.length - 1));
    if (page !== current) bookmark = page ? firstCharacter(starts[page].left) : 0;

    result.style.transform = page ? `translateX(${starts[0].left - starts[page].left}px)` : '';
    prev.disabled = page === 0;
    next.disabled = page === starts.length - 1;
    const label = !length && result.textContent ? 'Только пробелы'
      : `${columns > 1 ? 'Разворот' : 'Лист'} ${page + 1} из ${starts.length}`;
    if (position.textContent !== label) position.textContent = label;
  }

  function show(text) {
    const visible = text.replace(/ +$/u, '');
    flow.replaceChildren();
    runs = [];
    length = 0;
    bookmark = 0;
    // HTML lays out LF and CRLF natively. Bare CR needs an explicit line break.
    for (const part of visible.split(/(\r(?!\n))/u)) {
      if (!part) continue;
      const node = part === '\r' ? document.createElement('span') : document.createTextNode(part);
      flow.append(node);
      runs.push({node, start: length});
      length += part.length;
      if (part === '\r') {
        node.textContent = part;
        node.style.display = 'inline-block';
        flow.append(document.createElement('br'));
      }
    }
    result.replaceChildren(flow);
    if (visible.length < text.length) {
      const padding = document.createElement('span');
      padding.hidden = true;
      padding.textContent = text.slice(visible.length);
      result.append(padding);
    }
    layout();
    document.fonts.ready.then(scheduleLayout);
  }

  function clear() {
    result.replaceChildren();
    flow.replaceChildren();
    runs = [];
    result.style.transform = '';
    position.textContent = '';
    prev.disabled = next.disabled = true;
  }

  prev.addEventListener('click', () => layout(-1));
  next.addEventListener('click', () => layout(1));
  viewport.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    layout(event.key === 'ArrowLeft' ? -1 : 1);
  });

  let frame = 0;
  function scheduleLayout() {
    if (!frame) frame = requestAnimationFrame(() => {
      frame = 0;
      layout();
    });
  }
  const observer = new ResizeObserver(scheduleLayout);
  for (const node of [flow, result, paper, ...document.querySelectorAll('.reader-tools, .book-heading')]) {
    observer.observe(node, {box: 'border-box'});
  }
  lookup?.addEventListener('toggle', scheduleLayout);
  window.addEventListener('resize', scheduleLayout);
  document.fonts.ready.then(scheduleLayout);
  document.fonts.addEventListener('loadingdone', scheduleLayout);
  window.BabelReader = {show, clear};
})();
