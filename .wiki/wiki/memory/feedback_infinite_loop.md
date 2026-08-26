---
name: Infinite Improvement Loop Strategy
description: Run test→log→analyze→fix→retest loop indefinitely until all 25 games solved, no rush for quick results
type: feedback
---

빠른 성과보다 최종 완성도 우선. 마지막 분기(~2026-10) 전까지 모든 게임 해결이 목표.

**Why:** 대회 점수는 25개 게임 전체 평균이므로, 하나라도 더 푸는 게 중요. 각 접근법(CNN, 앙상블, Graph, Diff)이 서로 다른 게임을 풀므로 모두 유지하며 개선.

**How to apply:**
1. 테스트 → 로그 확인 → 분석 → 버그 수정/전략 강화 → 재테스트 무한 루프
2. CNN은 MAX_ACTIONS 무제한으로 테스트 (시간 오래 걸려도 OK)
3. 게임별 최적 접근법 매핑 유지
4. 모든 접근법 병렬 개선 (하나를 버리지 않음)
5. 성과 나면 최적화 (속도, Kaggle 6시간 제약 맞추기)
