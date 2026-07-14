codex
Rule **(c): drop PLAN from R55**.

Exact parameters:

- Design: **Base vs NAV**
- Games: **ls20, g50t, tu93**
- Replicates: **3 per cell per game**
- Total: **2 × 3 × 3 = 18 runs**
- Code/trigger specification: **d421beb**
- NAV cap: **4 fires/run**
- Audit: **OFF**
- PLAN: **no cells, no PLAN payload, no milestone elicitation, no goal-only relaxation**
- Pairing: retain the existing matched trace/seed assignment across Base and NAV
- Interpretation: R55 estimates the NAV effect only; PLAN receives **no effect estimate** and its replay failure is recorded as a pre-launch exposure-gate failure.

Keep the frozen PLAN eligibility rule—both goal and milestone nonempty—for its later return. This avoids silently changing the PLAN construct or bundling elicitation into the treatment after seeing replay results.
tokens used
