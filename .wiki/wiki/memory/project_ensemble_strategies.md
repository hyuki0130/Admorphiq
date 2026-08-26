---
name: Ensemble Agent Strategy Inventory
description: Current ensemble strategy count, categories, and target games for each new strategy
type: project
---

## 앙상블 전략 현황 (54개, 4749줄)

### 카테고리별 전략

| 카테고리 | 전략 수 | 주요 전략 |
|---------|--------|----------|
| Movement (sustained/zigzag) | 5 | sustained, zigzag, long_sustained, wall_avoid, spiral |
| Click | 10 | click_rare, raster, click_diff_track, click_all_colors, click_progressive, click_color_order, click_toggle, click_frame_adaptive, click_pixel_scan, click_grid_aligned |
| Navigation | 6 | navigate, bfs_explore, bfs_navigate, wall_map_nav, target_chase, smart_navigate |
| Hybrid (move+click) | 6 | move_click, move_then_click_grid, move_click_at_player, move_launch_click, sidescroll_click, click_select_move |
| Puzzle | 5 | slot_value_cycle, spell_cast, click_rotation_puzzle, sprite_cycle_match, scan_swap_puzzle |
| Special A5 | 4 | action5_cycle, action5_special, sokoban_interact, multi_character |
| Game-specific | 4 | platformer, maze_multiphase, grab_and_deliver, click_select_then_move |
| Exploration | 5 | explore_and_interact, action_sequence_search, graph_explore, pattern_repeat, all_combos |
| Meta | 4 | dominant_action, navigate_to_rare, grid_walk, move_collect, transform_detect |
| Multi-level | 2 | extended_winner, continue_multilevel |

### 최근 추가 전략 (이번 세션)

1. strat_multi_character — RE86 타겟 (A5 캐릭터 전환)
2. strat_sidescroll_click — BP35 타겟 (좌우+클릭)
3. strat_click_grid_aligned — SU15/TN36 타겟 (그리드 정렬 클릭)
4. strat_sprite_cycle_match — TR87 타겟 (패턴 변환)
5. strat_scan_swap_puzzle — SB26 타겟 (스캔+스왑)
6. strat_grab_and_deliver — WA30 타겟 (픽업/배달)
7. strat_click_select_then_move — SK48 타겟 (멀티 엔티티)

### 미해결 게임 분석

- SC25: spell_cast 전략 있음, 좌표/패턴 맞지만 미클리어. display_to_grid 변환 문제?
- DC22: 버튼 클릭으로 다리/벽 토글 + 이동. LLM이 4레벨 깸.
- SU15: 과일 매칭 체인 (4px 그리드). click_grid_aligned로 시도 중.
- TN36: 패널 편집 (A6 only). 매우 추상적.

**Why:** 각 전략은 특정 게임 유형에 맞춤. 하나라도 새 게임 클리어하면 대회 점수 상승.
**How to apply:** 테스트 결과 분석 후 실패한 게임에 맞춰 전략 수정/추가.
