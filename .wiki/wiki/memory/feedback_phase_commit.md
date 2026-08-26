---
name: Phase Commit Convention
description: Commit per phase with docs update, code review, and push convention
type: feedback
---

Phase 단위로 커밋하며, 매 Phase 완료 시 docs 에이전트가 문서 현행화, reviewer가 코드리뷰 후 커밋한다.

**Why:** 단계별 추적 가능성 확보, 문서와 코드의 동기화 유지.

**How to apply:**
- Phase 완료 → docs가 README.md + CLAUDE.md 현행화 → reviewer가 코드리뷰 + 커밋
- 커밋 메시지: `feat: complete Phase N — <title>`
- 실패 기록도 문서에 반영 (CLAUDE.md의 "Lessons Learned" 등)
