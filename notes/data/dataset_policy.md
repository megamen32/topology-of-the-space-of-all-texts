# Dataset candidates

Goal: train ordering models over byte pages, not store pages.

Recommended mix:

1. Russian books/public-domain text
   - PleIAs/Russian-PD on Hugging Face: large public-domain Russian monographies and periodicals.
   - GitHub/Kaggle russian_literature collections can be used as smaller quick-start corpora.

2. English books/public-domain text
   - Project Gutenberg-derived corpora or Common Corpus public-domain text.

3. Conversational style
   - OPUS/OpenSubtitles, especially ru/en monolingual or parallel subtitles.
   - Good for short phrase/dialogue distribution, closer to Telegram than books.

4. Encyclopedic neutral text
   - Wikimedia dumps / cleaned Wikipedia datasets for ru/en.

Initial training mix suggestion:

```text
40% ru books
20% en books
20% ru/en subtitles
20% ru/en Wikipedia
```

Reason: pure books make the beginning too literary; pure subtitles make it too fragmented.
