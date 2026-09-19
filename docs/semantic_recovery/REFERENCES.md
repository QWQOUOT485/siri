# Research and Technical References

These references motivate the retrieve-before-generate and candidate-constrain-before-LLM pattern. They do not define this project's production thresholds; project thresholds require local measurement.

## ASR named-entity correction

- Raghuvanshi et al., **Entity resolution for noisy ASR transcripts**, EMNLP-IJCNLP 2019  
  https://aclanthology.org/D19-3011/

- Wang et al., **DANCER: Entity Description Augmented Named Entity Corrector for Automatic Speech Recognition**, LREC-COLING 2024  
  https://aclanthology.org/2024.lrec-main.387/

- Luo et al., **Generative Annotation for ASR Named Entity Correction**, EMNLP 2025  
  https://aclanthology.org/2025.emnlp-main.1052/

- Singh et al., **Graph-Based Phonetic Error Correction of Noisy ASR**, ACL Industry 2026  
  https://aclanthology.org/2026.acl-industry.151/  
  arXiv: `2606.24889`

## Local lexical/fuzzy retrieval

- RapidFuzz process API  
  https://rapidfuzz.github.io/RapidFuzz/Usage/process.html

- SQLite FTS5 / trigram tokenizer  
  https://www.sqlite.org/fts5.html

- SymSpell (reference only; not Phase 1)  
  https://github.com/wolfgarbe/SymSpell

- marisa-trie — compact static trie reference for future prefix-oriented retrieval  
  https://github.com/pytries/marisa-trie

## Future local vector candidates

Not selected for Phase 1:

- sqlite-vec — local SQLite vector extension; upstream currently describes it as pre-v1, so breaking changes must be expected  
  https://github.com/asg017/sqlite-vec

- hnswlib  
  https://github.com/nmslib/hnswlib

## Spotify

- Spotify Web API — Search for Item  
  https://developer.spotify.com/documentation/web-api/reference/search

## Project decision

Phase 1 intentionally uses SQLite + RAM exact alias index + RapidFuzz candidate retrieval. The first preferred scale-up experiment is SQLite FTS5 as a lexical prefilter followed by RapidFuzz reranking, and only if Windows-host benchmarks show the full scan is materially expensive. SymSpell/trie approaches remain optional measured experiments. Vector search remains deferred until a real user-utterance corpus demonstrates incremental benefit. See `SEARCH_OPTIMIZATION.md` for the layered retrieval roadmap.
