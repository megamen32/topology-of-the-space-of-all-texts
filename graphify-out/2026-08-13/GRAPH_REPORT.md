# Graph Report - babel-experiments  (2026-08-13)

## Corpus Check
- 118 files · ~2,309,934 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 643 nodes · 886 edges · 104 communities (72 shown, 32 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e0e5df76`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- build_paragraph_student_v1.py
- build_sentence_student_v1.py
- fsm_astar_frontier.py
- run_hierarchical_students_pipeline.sh
- run_sentence_student_pipeline.sh
- run_word_student_pipeline.sh
- graphify-semantic.sh
- AGENTS.md
- clone_tg_economic.sh
- install_dataset_deps.sh
- dataset_policy.md
- eval_harness_v1.md
- eval_harness_v2.md
- experiment_b2_sentence_paragraph_frontier.md
- experiment_c_hierarchical.md
- markov3_vs_transformer.md
- markov_scaling.md
- 01_raw_bijection.md
- 02_fsm.md
- 03_hierarchical.md
- 04_evaluation.md
- 05_cluster.md
- 06_ranking.md
- ranking_plan.md
- worklog.md
- deploy-babel-walk.sh
- enable-babel-walk-tls.sh
- README.md

## God Nodes (most connected - your core abstractions)
1. `ClusterRanker` - 18 edges
2. `RawClusterRanker` - 17 edges
3. `HierarchicalEnumeratorV1` - 14 edges
4. `ChunkedRawCounter` - 11 edges
5. `main()` - 10 edges
6. `main()` - 9 edges
7. `ExactStudentRanker` - 9 edges
8. `boot()` - 9 edges
9. `boot()` - 9 edges
10. `boot()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `exact_cluster_ranker()` --calls--> `RawClusterRanker`  [INFERRED]
  experiments/backend_app.py → experiments/cluster_counting_mvp.py
- `main()` --calls--> `exact_cluster_ranker()`  [INFERRED]
  experiments/build_russian_walk.py → experiments/backend_app.py
- `ChunkedRawCounter` --uses--> `RawClusterRanker`  [INFERRED]
  experiments/cluster_chunk_counting.py → experiments/cluster_counting_mvp.py

## Import Cycles
- None detected.

## Communities (104 total, 32 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.13
Nodes (11): ClusterRanker, main(), parse_path(), Path, Exact ranker for fixed-length pages over the project's 256-symbol alphabet., Count raw-symbol suffixes, aggregating symbols by destination cluster., Exact energy-ordered enumerator for fixed-length cluster paths., Exact suffix count over behaviorally equivalent transition rows. (+3 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (21): api_counting_proof(), api_exact_neighbor(), api_generate(), api_rank(), api_russian_walk(), api_score(), api_search(), api_unrank() (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (21): boot(), cls(), detok(), escapeHtml(), generateFSM(), generateSentenceFromTemplate(), generateSentenceStudent(), hashSeed() (+13 more)

### Community 3 - "Community 3"
Cohesion: 0.22
Nodes (20): attachExpand(), B64MAP, boot(), decimalSci(), decodeAddressInput(), decodePage64(), encodeFixedPage64(), encodePage64() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (7): cls(), isCombining(), normalizeText(), normChar(), pageFromText(), rankText(), scoreText()

### Community 5 - "Community 5"
Cohesion: 0.29
Nodes (16): corpus_profile(), detok(), gen_fsm(), gen_paragraph(), gen_sentence(), gen_sentence_from_template(), gen_word(), generate() (+8 more)

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (5): demo(), HierarchicalEnumeratorV1, ParagraphShape, Foundational exact hierarchy layer.      NOT yet a production counter.      Purp, SentenceTemplate

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (16): 1. Long-page exact counting, 2. Paragraph hierarchy, 3. Energy compression, 4. Distilled transformer student, Canonical direction, Core idea, Hierarchical Student Master Note, Historical hierarchy direction (+8 more)

### Community 8 - "Community 8"
Cohesion: 0.27
Nodes (15): build_dp(), count_less_cost(), default_costs(), explain_first(), main(), rank_page(), rank_within_cost(), Return positive integer byte costs derived from -log2 probability.      smoothin (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.28
Nodes (15): boot(), buildTinyRanker(), detok(), generateFSM(), generateParagraphStudent(), generateSentenceFromTemplate(), generateSentenceStudent(), isPunct() (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.28
Nodes (6): ChunkedRawCounter, main(), Counter, Apply one exact raw-symbol transition to a state/energy vector., Return T[source][destination][energy] for exactly ``span`` steps., Count every raw page exactly, composing complete blocks then a tail.

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (13): Chunked page counting, Core insight, Counting strategy, Critical requirement, External-memory frontier, Hierarchical layers, Immediate implementation tasks, Main unresolved problem (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (12): 1. Long-page exact counting, 2. Hierarchical factorization proof, 3. Sentence/template composition, 4. Energy normalization, 5. Production-scale student_rank, Core idea, Current direction, Current unfinished areas / TODO (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.41
Nodes (12): boot(), detok(), generateCluster(), generateClusterV2(), generateFSM(), generateParagraph(), generateSentence(), generateSentenceFromTemplate() (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.17
Nodes (11): Current blocker, Goal, Hierarchical Student — Completion Roadmap, Introduce integer energies, Minimal grammar, Phase 1 — Freeze the hierarchy, Phase 2 — Unified energy model, Phase 3 — Exact compositional counting (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.18
Nodes (10): 1. Hidden-state clustering, 2. VQ-VAE / vector quantization, 3. Finite-state abstraction, Cost model, Current ladder, MVP 3 / MVP 4: token automaton and discretized transformer, MVP 3: token automaton, MVP 4: tiny transformer teacher (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (10): Conclusion, Emerged automatically, Emergent Structure and Next Steps, Existing groundwork, Goal, Manually specified, Next step — Cluster Student, Phase 1 — Raw bijection (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.42
Nodes (10): boot(), cfgName(), esc(), nextPair(), renderPair(), renderVotes(), rows, sampleFrom() (+2 more)

### Community 19 - "Community 19"
Cohesion: 0.42
Nodes (10): api(), boot(), compactCount(), current(), pageFromHash(), pages, setIndex(), showNeighbor() (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.20
Nodes (9): Current architecture, Goal, How to connect, Product / architecture decisions, Student design, Teacher choice, Why finite student, Why this matters (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.53
Nodes (8): conv(), human_int(), main(), mat_mul(), Counter, run(), trim_poly(), vec_mul()

### Community 22 - "Community 22"
Cohesion: 0.39
Nodes (6): fail(), log(), main(), need_file(), run_step(), run_pipeline.sh script

### Community 23 - "Community 23"
Cohesion: 0.42
Nodes (7): detok(), generate_sentence(), main(), paragraph_frontier(), realize(), sentence_frontier(), type_ok()

### Community 24 - "Community 24"
Cohesion: 0.53
Nodes (8): boot(), codeInfo(), esc(), fmt(), labelChar(), pct(), renderBars(), renderSummary()

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (3): Path, write_texts(), Redirect

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (7): Current Roadmap, Step 1 — Freeze current truth, Step 2 — Make cluster student v2 the explicit main path, Step 3 — Implement exact cluster counting MVP, Step 4 — Add rank/unrank prototype over cluster graph, Step 5 — Scale counting, Step 6 — Rewrite proof around current architecture

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): Advantages, Algorithm, B1 result: class-FSM collapse, Disadvantages, Experiment B — A* Low-Energy Frontier, Next: B2 sentence/word frontier, Status

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (7): Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6 (current), Project Phase Summary

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (7): Core goal, Current architecture, Current status, Read order, Repository structure, Topology of the Space of All Texts, Why this project exists

### Community 30 - "Community 30"
Cohesion: 0.54
Nodes (7): api(), baseRank(), boot(), exactRank(), rankAddress(), selectedLength(), selectedMode()

### Community 31 - "Community 31"
Cohesion: 0.48
Nodes (4): build_clusterer(), build_model(), sentence_energy(), tokenize()

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (6): 1. Exact cluster counting, 2. Production-scale energy frontier, 3. Rank/unrank over cluster student v2, 4. Polynomial/generating-function path, 5. Proof document, Open Problems

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (6): Current status, Legacy: class-FSM student, Replacement direction, What it is, What it proved, Why it is legacy

### Community 34 - "Community 34"
Cohesion: 0.62
Nodes (6): esc(), load(), render(), showCluster(), summarizeFromMapping(), topTransitions()

### Community 35 - "Community 35"
Cohesion: 0.67
Nodes (5): beam(), greedy(), load_model(), main(), state_of()

### Community 36 - "Community 36"
Cohesion: 0.53
Nodes (4): is_running(), taskctl.sh script, usage(), write_status()

### Community 37 - "Community 37"
Cohesion: 0.33
Nodes (5): Current main path, Current Status, Done, Important correction, In progress

### Community 38 - "Community 38"
Cohesion: 0.33
Nodes (5): Counting Infinity — Experiments, Experiment A, Experiment B, Experiment C, Experiment D

### Community 39 - "Community 39"
Cohesion: 0.33
Nodes (5): Alphabet and corpus, Counting Infinity — Results, Exact rank MVP, Markov ladder, Student models

### Community 40 - "Community 40"
Cohesion: 0.60
Nodes (3): call_ollama(), gibberish_score(), judge_pair()

### Community 41 - "Community 41"
Cohesion: 0.60
Nodes (3): chat(), gibberish_score(), judge_pair()

### Community 42 - "Community 42"
Cohesion: 0.40
Nodes (4): Action plan: human-ordered bijective Babel, Do not do yet, Goal, Minimum path

### Community 43 - "Community 43"
Cohesion: 0.40
Nodes (4): Markov as a measurement instrument, Markov Theory Notes, Proof-first vs quality-first, Scaling observations

### Community 44 - "Community 44"
Cohesion: 0.70
Nodes (4): boot(), card(), esc(), tryFetch()

### Community 45 - "Community 45"
Cohesion: 0.70
Nodes (4): boot(), cfgName(), esc(), metricCards()

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (3): Babel enumerative MVP, Proof sketch, Run

### Community 47 - "Community 47"
Cohesion: 0.83
Nodes (3): human_int(), main(), run()

### Community 50 - "Community 50"
Cohesion: 0.50
Nodes (3): General observation, Markov Experimental Results, Observed behavior

### Community 51 - "Community 51"
Cohesion: 0.50
Nodes (3): Counting Infinity, The challenge, Why brute force does not work

### Community 52 - "Community 52"
Cohesion: 0.50
Nodes (3): Current Architecture, Main student, Product surface

## Knowledge Gaps
- **153 isolated node(s):** `clone_tg_economic.sh script`, `install_dataset_deps.sh script`, `deploy-babel-walk.sh script`, `enable-babel-walk-tls.sh script`, `graphify-semantic.sh script` (+148 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RawClusterRanker` connect `Community 0` to `Community 1`, `Community 10`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Why does `ChunkedRawCounter` connect `Community 10` to `Community 0`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `RawClusterRanker` (e.g. with `exact_cluster_ranker()` and `ChunkedRawCounter`) actually correct?**
  _`RawClusterRanker` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `clone_tg_economic.sh script`, `install_dataset_deps.sh script`, `deploy-babel-walk.sh script` to the rest of the system?**
  _153 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12857142857142856 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.14666666666666667 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.13157894736842105 - nodes in this community are weakly interconnected._