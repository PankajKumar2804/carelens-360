# Run of show

Six minutes. Order matters — each step answers a different thing someone might doubt.

**Open.** A care manager has 200 patients across four systems and a payer policy PDF. Today that's three tools and a phone call. Mention up front that everything is synthetic, so nobody spends the demo wondering.

**1. The Copilot Interface.** Open the CareLens 360 Copilot app. Point out how everything is unified in a single chat interface.

**2. Lightning Fast Retrieval.** Ask for the sacubitril/valsartan coverage criteria and the appeal window. Emphasize the ultra-low latency response powered by Claude Haiku 3.5. Open the evidence panel — `PA-CARD-014 — Coverage Criteria`, and the 60-day window quoted from the source.

**3. The question that needs both halves.** "Which heart failure patients have no ARNI, MRA or SGLT2 on file, and which policy governs that gap?" Watch the tool trace go policy → semantic view → per-patient table. Then open the Generated SQL tab: the number is as checkable as the quote.

**4. The one it won't answer.** Ask for a warfarin dose. It declines and says nothing in the corpus supports it. "In a clinic, what it won't say matters more than what it will."

**5. Governance isn't a slide.** Re-run the same patient query as the analyst role. Names redacted, DOB down to year, notes withheld. Same agent, same question. Policies evaluate under the caller, so the copilot inherits permissions rather than reimplementing them.

**6. It's measured and secure.** Close on the CoCo CLI layer — the hook blocks unsafe loads, the auditor service re-derives claims, `AGENTS.md` makes the constraints something the tooling enforces on me.
