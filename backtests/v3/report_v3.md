# V3 feature ablation

Families are accepted only on training folds; 2025/26 is never used for selection.

Final families: **team_continuity+underlying_multiseason**
V3 Spearman: **0.332**
V1: **0.350**
Persistence: **0.360**
Lift vs V1: **-0.018**
Lift vs persistence: **-0.027**
Understat source: **understat-github-mirror**, xG coverage **8.8%**

| prior_season   | target_season   |   training_folds |   evaluated_players | selected_families                      |   v1_spearman |   persistence_spearman |   v3_spearman |   v3_top20 |   v1_top20 |   persistence_top20 |   v3_ndcg50 |   persistence_ndcg50 | understat_available   | understat_source        |   xg_coverage | is_final_holdout   |   v3_lift_vs_v1 |   v3_lift_vs_persistence |
|:---------------|:----------------|-----------------:|--------------------:|:---------------------------------------|--------------:|-----------------------:|--------------:|-----------:|-----------:|--------------------:|------------:|---------------------:|:----------------------|:------------------------|--------------:|:-------------------|----------------:|-------------------------:|
| 2021-22        | 2022-23         |                2 |                 342 | xg_regression                          |      0.417114 |               0.429068 |      0.374373 |   0.324565 |   0.30894  |            0.31981  |    0.673319 |             0.70991  | True                  | understat-github-mirror |     0.0584795 | False              |      -0.0427409 |               -0.0546948 |
| 2022-23        | 2023-24         |                3 |                 323 | vote_stability                         |      0.437145 |               0.423078 |      0.41058  |   0.397619 |   0.397619 |            0.375298 |    0.722449 |             0.717651 | True                  | understat-github-mirror |     0.0866873 | False              |      -0.0265648 |               -0.0124979 |
| 2023-24        | 2024-25         |                4 |                 339 | team_continuity                        |      0.358745 |               0.390683 |      0.328807 |   0.415803 |   0.415803 |            0.404934 |    0.693422 |             0.739561 | True                  | understat-github-mirror |     0.0678466 | False              |      -0.0299381 |               -0.0618761 |
| 2024-25        | 2025-26         |                5 |                 351 | team_continuity+underlying_multiseason |      0.350212 |               0.359637 |      0.332436 |   0.419339 |   0.419339 |            0.419339 |    0.706097 |             0.691583 | True                  | understat-github-mirror |     0.0883191 | True               |      -0.0177758 |               -0.0272006 |