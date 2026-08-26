---
name: Development Loop Convention
description: Failure → document → redesign → delegate → test → repeat loop for all development work
type: feedback
---

실패 시 반드시 문서화하고, 처음부터 재설계한 후 에이전트에 위임하여 개발/테스트하는 루프를 지속 반복한다.

**Why:** 실패를 기록하지 않으면 같은 실수를 반복하고, 부분 수정보다 재설계가 더 깨끗한 결과를 만든다.

**How to apply:**
1. 실패 발생 → 원인과 증상을 문서에 기록
2. 기존 접근법 폐기, 처음부터 재설계
3. 에이전트에 위임 (ml-engineer, infra 등)
4. tester/reviewer가 검증
5. 실패하면 1번으로 돌아가서 반복
6. Phase 커밋은 테스트 통과 후에만
