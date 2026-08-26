---
name: LLM Drives the Game-Completion Loop, Not Claude Code
description: Qwen is the game-completion agent — comprehend / pick / execute / fix. Claude Code is the implementation helper for code fixes Qwen proposes, not the unilateral designer
type: feedback
originSessionId: eba5cc76-48c0-4391-bce2-39b48288934e
---
The offline LLM (Qwen 3 family) is the **primary agent** for
Admorphiq's Kaggle-time game completion. Its role covers:

1. Game comprehension from DiscoveryReport + wiki retrieval.
2. Plan fn selection from the LLM-visible whitelist.
3. Runtime failure observation when a plan returns 0 levels /
   regresses / times out.
4. **Self-correction**: pick a different plan, retune parameters,
   OR propose a code fix to the failing plan fn.

Dev-time Claude Code is the **implementation helper**: receive
Qwen's diagnosis + fix proposal, write the code change, commit,
re-bench. Claude Code does not unilaterally redesign plan fns
from its own reading of probe traces.

**Why**: the user confirmed this framing on 2026-04-23 over two
successive messages:
  - "Qwen 은 단순 라우팅 뿐만 아니라 오류 있으면 어떻게 코드
    수정하는게 좋을지 스스로 판단하고 self-healing 하면서 게임
    complete 하는게 목표로 하는거야"
  - "게임 파악하고 게임 실행을 함수로 실행하는거 역시 llm 이
    하니깐 얘가 함수 잘못된것도 스스로 생각해서 수정하면서 할
    수 있어야해! 넌 그걸 돕는거야"

Rounds R16-R22 (2026-04-23) violated this: R11's single-item
allowlist zeroed Qwen's voice, so Claude Code read direct-test
results and edited plan fns directly. The code itself is fine
(generic, no game-title branching), but the PROCESS was wrong.

**How to apply**:
- Each dev-time round must start with a Qwen bench run producing
  failure envelopes — not a Claude-Code-only direct-probe.
- When Qwen fails on a level, capture its self-healing response
  (plan swap / parameter retune / CodeFixProposal) from the trace.
- Claude Code reads the proposals and implements them; does NOT
  start from its own analysis.
- The LLM allowlist must be rich enough that Qwen has real choice
  (R11's single-item allowlist is the current bottleneck, tagged
  for rollback in R23).

**Exception**: genuine infrastructure bugs (regressions measured
against baseline, failing tests) may be fixed by Claude Code
directly with a passing-test commit. But new plan fns, new
heuristics, new cell-selection strategies — those all need Qwen's
diagnosis first.
