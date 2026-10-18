# Commercial Auto Submission Review (Knight Insurance exercise)

Local web app: load one submission packet (PDF/CSV/TXT, or paste the broker email), extract fields with an LLM
(with source evidence), run rules R1-R5 in plain code, show an AI summary and an **editable draft** broker email
(never sent), and let a reviewer correct a field and re-run the checks.

## Setup and run
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill ONE provider (see below)
python -m app.server        # open http://127.0.0.1:5000
python -m pytest -q         # tests: no network / no model needed
```
Python 3.10+. Sample packets are in `samples/SUB-A|B|C` (copied from the supplied materials).

## Model / provider
Set in `.env` (no keys in source):
| LLM_PROVIDER | needs | default model |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `gemini-3.8-flash` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` (override with `LLM_MODEL`) |
| `openai_compatible` | `OPENAI_BASE_URL`, `OPENAI_API_KEY` | `gpt-4o-mini` |
| `ollama` (free, local) | `ollama pull llama3.1:8b` | `llama3.1:8b` |

**Provider/model used for my demo:** _<fill in>_  **AI coding tools used:** _<fill in>_  **Time spent:** _<fill in>_

## Architecture
```
upload -> ingest.py (read + classify files, attachment inventory)
       -> extract.py  explicitly labeled values are parsed deterministically; LLM extracts fields from
                      unstructured sources/fields. Code verifies evidence against the source, computes locator
                      (PDF page / email body), normalizes (normalize.py), merges email+PDF, detects CONFLICT
                      schedule count (CSV) and loss-runs presence (inventory) are derived WITHOUT the LLM
       -> service.py  effective value = human override if present, else extracted (original evidence kept)
       -> rules.py    R1-R5, deterministic, no I/O
       -> narrative.py LLM writes summary + draft email from the verified facts only
server.py (Flask JSON API) + static/index.html (vanilla JS UI)
```
Key decisions
- **Rules never see the LLM.** They consume typed values + states (`KNOWN/MISSING/CONFLICT/INVALID`).
- **Evidence is verified in code.** A model value whose quote can't be found in the source is discarded and the
  field is shown as unresolved (R-rules -> UNKNOWN), so hallucinated or prompt-injected values can't become facts.
- **Hybrid extraction and failure handling.** Clearly labeled field/value lines are parsed deterministically and
  merged across sources. If the LLM is unavailable, verified labeled values and attachment-derived results remain
  usable; fields that need model extraction are shown as unresolved rather than guessed.
- **Conflicts** keep both alternatives with evidence, value = null, no source preferred. "Not provided" is not a conflict.
- **Absence vs failure:** if the model call fails, text fields become unresolved (UNKNOWN), never "absent" (FLAG).
  Deterministic results (vehicle count, loss runs, R5) still display. Narrative failure shows an error and a
  clearly labelled non-AI template email.
- Packets are independent: each upload creates a fresh in-memory submission; "Clear" wipes the UI.

## Known limitations
- `operations_description` is compared after case/whitespace/trailing-punctuation normalization; any real wording
  difference between email and PDF is reported as CONFLICT.
- Dates: only ISO `YYYY-MM-DD` and "Month D, YYYY" are accepted; `11/01/2026` is INVALID rather than guessed.
- No OCR (scanned PDFs show as unreadable). No bounding-box viewer. In-memory storage (lost on restart).
- Multiple vehicle CSVs in one packet -> schedule count INVALID (ambiguous).
- Local models (e.g. 8B) may need the retry/verification path more often than a hosted model.
- Live-model behaviour was exercised with the provider configured above; unit/pipeline tests use a stub model.

## Tests
`tests/test_rules.py` (missing info, conflict, unequal counts, 150 / 150.0 / 150.1, R1 precedence),
`tests/test_normalize.py`, `tests/test_pipeline.py` (SUB-A/B/C end to end with a stub model, overrides keep original
evidence, packet independence, hallucination/injection rejection, model-failure behaviour).



Final Output and Summary
<img width="1917" height="967" alt="image" src="https://github.com/user-attachments/assets/54d30fdc-80e7-4b06-8915-9e5d1b54638a" />
<img width="1917" height="961" alt="image" src="https://github.com/user-attachments/assets/a96c5f22-71f3-4f88-b84c-aefb3052d122" />
<img width="1917" height="967" alt="image" src="https://github.com/user-attachments/assets/593d2250-ff06-41b4-9485-bc38b28622e2" />
<img width="1917" height="967" alt="image" src="https://github.com/user-attachments/assets/f97714f4-8d74-40cf-a137-eb4553e691a0" />






