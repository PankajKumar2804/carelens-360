# CareLens 360

A patient/member 360 plus a copilot that answers clinical and regulatory questions with actual
citations. Built on Snowflake with CoCo CLI.

Everything here runs on synthetic data. `scripts/gen_synthetic.py` makes it up from scratch —
fictional names, invented policy text, made-up discharge notes. The ICD-10 and LOINC codes are
real because I wanted the joins to behave like real joins, but nothing attached to them came from
a real person.

## Why I built it this way

The thing that annoys me about most healthcare AI demos is that you ask "why is this patient high
risk" and get a SHAP plot back. Nobody is going to act on that at 4pm on a Friday.

So the risk score here is just arithmetic. It's the LACE index — length of stay, whether the
admission was emergent, Charlson comorbidity, ED visits in the last six months. Four numbers you
add together. Every row stores its own explanation:

```
LACE 12 = L5 (last LOS 9d) + A3 (admission source EMERGENCY) + C3 (Charlson 3, capped at 5)
        + E1 (1 ED visits in prior 6 months)
```

That isn't an explanation generated after the fact. It *is* the calculation. If a clinician
disagrees, they can disagree with a specific input, which is the only kind of disagreement that's
actually useful.

I added two of my own modifiers — medication adherence below 0.80, and a documented barrier to
care pulled out of the discharge note. Those live in separate columns and roll into a differently
named score, because quietly bending a published index and still calling it LACE felt wrong.

## Getting it running

```bash
pip install snowflake-cli
snow connection add
# Use ./run.sh for macOS/Linux, or .\run.ps1 for Windows
./run.sh all      # generates data, deploys all eight SQL layers
./run.sh app      # pushes the Streamlit app
./run.sh demo     # runs the walkthrough queries end to end
```

What these commands do:
- **`all`**: Builds the entire project from scratch. It sets up the database, generates synthetic data, uploads it to Snowflake, and runs all 7 SQL scripts to build the views, agent specs, governance policies, and tests.
- **`app`**: Deploys the user interface by pushing `app/carelens_app.py` directly to Snowflake using the `deploy_app.ps1` script (or `run.sh app`).
- **`demo`**: Runs a presentation script (`demo/demo_queries.sql`) to verify the system works end-to-end.

Takes a few minutes. The Cortex Search services need a moment to index before the copilot is
useful, so if the first question comes back empty, wait and retry.

Inside CoCo CLI:

```
$carelens-360   # project conventions, where everything lives, how to extend it
$phi-guard      # privacy pre-flight, blocks you before you do something dumb
```

## What's in here

```
scripts/gen_synthetic.py      the data generator (seeded, so runs are reproducible)
sql/00_setup.sql              db, schemas, three personas, warehouse, stages
sql/01_load_structured.sql    COPY INTO, conformed layer, data quality checks
sql/02_documents.sql          parse → metadata → chunk → mine safety signals
sql/03_gold_360.sql           the 360 table, risk, care gaps, evidence ledger
sql/04_semantic_view.sql      semantic view for Cortex Analyst
sql/05_search_and_agent.sql   three search services + the agent spec
sql/06_governance.sql         masking, row access, audit log
sql/07_eval.sql               golden questions + an LLM judge
app/carelens_app.py           Streamlit UI (Single-page copilot interface)
.cortex/                      skills, services, hooks for CoCo CLI
```

Run the SQL in numeric order. `run.sh all` does that for you.

## The document side

76 documents. 70 are synthetic discharge summaries, the rest are prior-auth policies, drug safety
label summaries, a regulatory reporting bulletin, and a quality measure spec.

The pipeline is regex first, `AI_EXTRACT` second. Most of these documents have a predictable
header block, so pulling the doc ID and effective date with a regex costs nothing. `AI_EXTRACT`
only picks up what the regex missed, which means a new document layout doesn't break the pipeline
but a well-formed one doesn't cost me anything either.

Chunking splits on `\n## ` before anything else. That's deliberate — it means chunks line up with
document sections, so a citation can say "PA-CARD-014 — Coverage Criteria" instead of pointing at
a filename. The difference matters when someone has to go verify it.

There's a second `AI_EXTRACT` pass over the discharge notes that pulls out adverse events,
barriers to care, and follow-up intervals into a view. That view is where the structured and
unstructured sides actually meet: a barrier to care written in prose becomes a point on the risk
score.

## Access control

Three roles, and they see genuinely different things:

| | names | DOB | zip | clinical notes | rows |
|---|---|---|---|---|---|
| clinician | full | full | full | full | own clinics |
| care manager | initial + mask | year only | first 3 | full | entitled clinics |
| analyst | redacted | year only | first 3 | withheld | all, masked |

Masking policies and a row access policy, both evaluated at query time under whoever's asking.
The nice side effect is that the agent inherits all of this for free — it can't show you anything
you couldn't already query yourself, and there's no second permissions system to keep in sync.

Row access reads from an entitlement table rather than hardcoded role names, so adding a clinic is
an INSERT.

Free-text note content gets its own masking policy. Unstructured clinical text is the easiest
thing in the whole database to re-identify someone from, and the analyst role has no business
reading it.

## Does it stay grounded?

12 golden questions in `sql/07_eval.sql` covering structured aggregates, risk explanations,
document lookups, hybrid questions that need both halves, and audit requests. Each one records
which tools it *should* have used, so tool routing gets scored separately from answer quality. An
`AI_COMPLETE` call grades grounding, citation specificity, refusal correctness and completeness.

Question 10 asks for a warfarin dose. Nothing in the corpus covers it and the right answer is to
say so and stop. I care about that one more than the other eleven. A copilot that will confidently
answer a dosing question from model weights is worse than no copilot.

## Notes to self / things I'd fix

- The first data run had random readmission outcomes, which meant the LOW risk band showed a
  *higher* observed readmission rate than HIGH (48.7% vs 50.0%, basically noise). Embarrassing.
  Two bugs: the outcome was independent of the factors, and it was assigned per encounter while
  the risk table scores only the last inpatient stay — so a patient with six short admissions
  collected six coin flips and looked high-risk in the outcome while scoring LOW on the index.
  Generator now computes LACE the same way `sql/03` does and attaches the outcome to the index
  stay only. Bands come out 25.6% / 33.3% / 46.2% (`eval/risk_band_validation.csv`). Synthetic
  outcomes have to be internally consistent or the data argues against your own design.
- Band separation here proves the plumbing works, not that the index is calibrated for any real
  population. Real use needs local recalibration.
- The policy and drug label text is fictional. The *shape* is realistic, the content isn't
  authoritative, and every generated file says so in its footer.
- Care gap rules are approximations. The 14-day follow-up rule in particular uses a simplified
  exclusion set.
- Only 76 documents. Enough to prove retrieval and citation work, not enough to stress test.
- PDF/DOCX ingestion via `AI_PARSE_DOCUMENT` is written and commented out in `02_documents.sql`.
  I only had markdown to work with.
- No temporal versioning on the policies. Real prior-auth policies get revised and you need to
  know which version applied on the date of service.

## The CoCo CLI bits

I ended up treating the CLI tooling as part of the project rather than just an afterthought:

- **`carelens-360` skill** — project map, plus recipes for adding an entity, a document class, or
  a risk rule without breaking the citation chain.
- **`phi-guard` skill** — five checks with the SQL to prove each one, run before any data load.
  Refuses to report PASS on anything it didn't actually query.
- **`evidence-auditor` service** — takes an answer apart into individual claims and re-derives
  each one. Deliberately won't accept the answer's own citation label as proof.
- **`semantic-curator` service** — for when Cortex Analyst picks the wrong column. Analyst
  accuracy is a modelling problem, so it fixes the view rather than the prompt.
- **PreToolUse hook** — blocks schema drops, truncating the curated layer, removing a masking or
  row access policy, external stage loads into patient tables, and anything with an SSN-shaped
  string in it.

The hook is the part I'd defend hardest. "Synthetic data only" and "no black box risk scores"
aren't README promises here, they're things the dev environment won't let me break even when I'm
moving fast and not thinking.
