# Dataset source manifest

Downloaded now:

1. `raw/ruslit`  
   Source: `https://github.com/d0rj/RusLit`  
   Russian literature TXT corpus, UTF-8.

2. `raw/gutenberg`  
   Project Gutenberg English books, plain text where available.

3. `raw/opensubtitles-devtest`  
   Source: `https://github.com/Helsinki-NLP/OpenSubtitles-devtest`  
   Small OpenSubtitles development/test repository for dialogue-like text.

Deferred phase-2 sources:

1. PleIAs/Russian-PD on Hugging Face — large Russian public-domain collection.
2. Wikimedia ru/en dumps — very large neutral encyclopedic corpus.
3. Full OPUS/OpenSubtitles — large subtitle/dialogue corpus.

Reason for deferring: MVP needs manageable corpora first; ranking algorithm is the bottleneck, not raw dataset size.

## Added social/emoji candidates

Direct-download tasks:

1. Hugging Face `TatarNLPWorld/sovet_kinesh-vk`
   - VK posts/comments, Tatar/Russian code-switching, informal text and emoji stated in card.

2. Hugging Face `IlyaGusev/pikabu`
   - Russian posts/comments, streamed subset for MVP.

3. Hugging Face `AlexSham/Toxic_Russian_Comments`
   - Russian OK/comment-style toxic comments.

4. Hugging Face `cardiffnlp/tweet_eval`, config `emoji`
   - English Twitter emoji prediction benchmark.

5. GitHub `pavel805/TGEconomicDataset`
   - Russian Telegram economic-channel dataset; repo contains dumps/scripts.

Mendeley VK university publics:

- 2023-2024: https://data.mendeley.com/datasets/kf3s4xf33j/1, DOI `10.17632/kf3s4xf33j.1`.
- 2022-2023: https://data.mendeley.com/datasets/fvz9mrnjzy/1, DOI `10.17632/fvz9mrnjzy.1`.
- 2021-2022: https://data.mendeley.com/datasets/fcyfn32mv6/1, DOI `10.17632/fcyfn32mv6.1`.

Mendeley needs direct file/API resolution; tracked separately.
