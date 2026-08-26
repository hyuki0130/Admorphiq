---
name: project_cpu_dev_vm_ceph_build
description: "GCP credits EXHAUSTED (real money now) — for CPU-only work use the ceph-build VM instead: ssh -i ~/VM/keys/nfw-dev.pem ubuntu@ceph-build (64 cores/251GB RAM/Python 3.12). GCP only when GPU is truly required, with user awareness."
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**GCP free credits are EXHAUSTED as of 2026-07-15 — every GCP minute is real money**
(user directive 2026-07-15: "GCP는 크레딧 다 사용해서 비용이 나가고 있어").

**Default CPU workhorse = ceph-build VM (NOT GCP):**
- Access: `ssh -i /Users/nhn/VM/keys/nfw-dev.pem ubuntu@ceph-build`
  (wrapper: `~/VM/ssh/ceph-build.sh`; key path is relative — run from `~/VM/ssh/` or use absolute path).
- Specs measured 2026-07-15: **64 cores, 251GB RAM, 428GB free disk, Python 3.12.3**, Ubuntu.
  8x the cores of the GCP e2-standard-8 spot we were paying for — script25/full-25 CPU
  benches parallelize far better here, at zero cost.
- No repo yet: transfer via the same tar/scp recipe as [[project_dev_test_env]]
  (`uv` install + `tar czf` repo + scp + `uv sync`). Home dir has unrelated projects
  (ceph, freqtrade-bot) — keep ours under `~/admorphiq`.

**GCP policy from now on:** only for genuinely GPU-required runs (vLLM agent benches),
stated purpose+hours first, user-aware. GCP leftovers: instance `r56-cpu` (asia-east1-a)
is TERMINATED; its 50GB pd-standard disk still exists (~$2/month) and holds the raw
r56s1..s4 result JSONs — the headline numbers are already recorded in
[[project_r56_r58_state]] and the wiki, so the disk is deletable if the user wants
zero cost. Related: [[feedback_submission_user_decides]] (GPU frugality).
