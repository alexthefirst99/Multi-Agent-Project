# Interview Stories

One ~150-word, quantified, technical-interview-ready story per student,
following the framework from the assignment:

> Situation (what broke) → Action (the algorithmic guardrail you built) →
> Result (quantified before/after metrics).

Pull the actual numbers from each student's own `METRICS.md` once real
before/after runs exist — do not invent numbers here.

---

## 1. Student 1 — Coordinator / Infinite Graph Loops

TODO: ~150 words. Reference `student_1_loop/METRICS.md` for real loop-count
numbers once measured (e.g. "unbounded → capped at 5 rounds").

---

## 2. Student 2 — Worker A / Silent Hallucination

TODO: ~150 words. Reference `student_2_silent/METRICS.md` for real
schema-validation-failure-rate numbers before/after the structured-output
guardrail + self-correcting retry.

---

## 3. Student 3 — Worker B / Rogue Tool Execution

TODO: ~150 words. Reference `student_3_rogue/METRICS.md` for real
unauthorized-tool-call-block-rate numbers.

---

## 4. Student 4 — Validator / Downstream Cascade Failure

TODO: ~150 words. Reference `student_4_cascade/METRICS.md` for real
downstream-crash-rate numbers before/after the sanitize/assert node.

---

## 5. Student 5 — Global Tracing / Data Privacy Leak

TODO: ~150 words. Reference `student_5_trace/METRICS.md` for real
leaked-PII-record-count numbers before/after the redaction interceptor.

---

## 6. Student 6 — Global Context/Token Manager

TODO: ~150 words. Reference `student_6_tokens/METRICS.md` for real
token-spend / latency numbers before/after pruning+summarization.
