# Intent Capture — Questions

## Sources

- [desc] Initial description: "review the product requirements and check what can  be improved and ask me about it"
- [scope] Workflow-selected scope: `poc`.

## Q1. [Product owner] What should happen to REQUIREMENTS.md at the end of this work?

Context: you said the document may be restructured and eventually removed to fit the AI-DLC workflow. This decides what the final repo looks like.

- A. Delete it entirely once its content lives in the AI-DLC requirements records
- B. Replace it with a short product overview in `docs/` that links to the AI-DLC requirements records
- C. Keep a cleaned-up, human-readable product spec in `docs/` and treat the AI-DLC records as the working detail
- D. Not yet defined — decide after the review
- X. Other (please specify)

[Answer]: A

## Q2. [Product owner] What is the main reason for doing this review now?

Context: the trigger shapes how deep the critique goes (light tidy-up vs. a full rethink of features).

- A. I am about to build the next delivery phase and want a clean, trustworthy spec first
- B. I am adopting AI-DLC and want the project's requirements in its structure
- C. The spec has grown messy or inconsistent and I am no longer sure it describes what I want
- D. Not identified
- X. Other (please specify)

[Answer]: X. Other: "1 and 2" — both A (about to build the next delivery phase and want a clean spec first) and B (adopting AI-DLC and want the requirements in its structure)

## Q3. [Product owner] Who will read and rely on the requirements after this work?

Context: this tells me who the "customer" of the restructured docs is and how they should be written.

- A. Only me, as a solo developer
- B. Me plus AI agents doing the building (AI-DLC stages)
- C. Me plus future human contributors
- D. Not identified
- X. Other (please specify)

[Answer]: B

## Q4. [Product owner] Which documents should move into the new `docs/` directory?

Context: the repo root currently holds `README.md` and `REQUIREMENTS.md`.

- A. Only the requirements/product documentation; `README.md` stays at the root
- B. All Markdown documentation including `README.md` (with a minimal root README pointing to `docs/`)
- C. Requirements documentation plus any new docs created by this work (e.g. architecture overview); `README.md` stays at the root
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "requirements plus new docs unless the aidlc workflow puts these elsewhere and no docsdir is needed"

## Q5. [Product owner] What does this piece of work leave out? (select all that apply)

Context: naming the boundary keeps the review from drifting into building features.

- A. No changes to the application code (app.py, templates, static files)
- B. No brand-new features — only improve, clarify or cut the features already described
- C. No writing of actual opening-lesson content (the catalog stays a plan)
- D. None — anything is open for discussion
- X. Other (please specify)

[Answer]: D

## Q6. [Product owner] Where should the lasting product requirements live once REQUIREMENTS.md is deleted?

Context (follow-up to your Q4 answer): AI-DLC keeps requirements per piece of work, inside that work's own record (here `aidlc/spaces/default/intents/261111-requirements-review/inception/requirements-analysis/`). It also has a space-wide knowledge folder, `aidlc/spaces/default/knowledge/`, that every future piece of work reads. So the workflow already has homes for this content, and a `docs/` directory is only needed for docs meant for humans outside the workflow.

- A. Only in this work's requirements record; no `docs/` directory
- B. A lasting product vision and feature backlog in `aidlc/spaces/default/knowledge/` (read by all future work), plus this work's requirements record; no `docs/` directory
- C. A `docs/` directory at the root for human-facing docs (e.g. a product overview), plus the AI-DLC records
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "the pure ai dlc workflow methology "

## Consolidated Summary Confirmation

- REQUIREMENTS.md is deleted entirely once its content lives in the AI-DLC records (Q1).
- Why now: you are about to build the next delivery phase and want a clean spec first, and you are adopting AI-DLC and want the requirements in its structure (Q2).
- The requirements will be read and relied on by you plus the AI agents doing the building (Q3).
- No separate `docs/` directory unless the workflow needs one: the content goes where the AI-DLC methodology puts it — this work's requirements record, and the workflow's own space-wide knowledge folder where lasting content belongs (Q4, Q6).
- Nothing is ruled out up front: features, the opening catalog and even app changes are open for discussion in the review (Q5).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Assumption Confirmation

- [assumption] You are the sole decision-maker on the scope and priority of the requirements; the AI agents only consume them and influence nothing.
- [assumption] No communication requirement or reporting cadence applies beyond the approval steps of this workflow.

- A. Accept assumptions
- B. Convert to follow-up questions

[Answer]: A. Accept assumptions
