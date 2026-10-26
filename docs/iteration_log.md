# Iteration log

What broke, what changed, what was retested. The assessment asks for successes,
failures, revisions and retesting; this file is that record. Keep the old
numbers, do not overwrite them.

## Template

### YYYY-MM-DD — <what was being tested>

**Observed.** <what happened, with numbers>

**Diagnosis.** <why>

**Change.** <what was altered, in which file>

**Retest.** <the same run after the change, with numbers>

---

### Expected entries

Three scenarios are expected to defeat the first implementation. Record them
here when they do, rather than fixing them silently:

- Scenario 2, empty response: an argument-only fingerprint will miss it,
  because the agent keeps rephrasing the query.
- Scenario 6, flapping service: a consecutive-error counter resets on every
  other success and never trips.
- Scenario 14, slow but working: a breaker that treats latency as failure
  opens the circuit on a healthy service.
