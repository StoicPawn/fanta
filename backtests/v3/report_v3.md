# V3 feature ablation

Families are accepted only on training folds; 2025/26 is never used for selection.

Final families: **multiseason+team_continuity+vote_stability**
V3 Spearman: **0.348**
V1: **0.349**
Persistence: **0.360**
Lift vs V1: **-0.001**
Lift vs persistence: **-0.011**
Understat source: **understat-github-mirror**, xG coverage **8.8%**

| prior_season   | target_season   |   training_folds |   evaluated_players | selected_families                          |   v1_spearman |   persistence_spearman |   v3_spearman |   v3_top20 |   v1_top20 |   persistence_top20 |   v3_ndcg50 |   persistence_ndcg50 | understat_available   | understat_source        |   xg_coverage | is_final_holdout   |   v3_lift_vs_v1 |   v3_lift_vs_persistence |
|:---------------|:----------------|-----------------:|--------------------:|:-------------------------------------------|--------------:|-----------------------:|--------------:|-----------:|-----------:|--------------------:|------------:|---------------------:|:----------------------|:------------------------|--------------:|:-------------------|----------------:|-------------------------:|
| 2021-22        | 2022-23         |                2 |                 342 | xg_regression                              |      0.411811 |               0.429068 |      0.374199 |   0.324565 |   0.31981  |            0.31981  |    0.68049  |             0.709967 | True                  | understat-github-mirror |     0.0584795 | False              |    -0.0376121   |               -0.0548694 |
| 2022-23        | 2023-24         |                3 |                 323 | multiseason                                |      0.432608 |               0.423078 |      0.408681 |   0.447619 |   0.385714 |            0.375298 |    0.702615 |             0.717637 | True                  | understat-github-mirror |     0.0866873 | False              |    -0.0239265   |               -0.0143972 |
| 2023-24        | 2024-25         |                4 |                 339 | multiseason                                |      0.3598   |               0.390683 |      0.349042 |   0.404934 |   0.394064 |            0.404934 |    0.697878 |             0.739561 | True                  | understat-github-mirror |     0.0678466 | False              |    -0.0107585   |               -0.0416412 |
| 2024-25        | 2025-26         |                5 |                 351 | multiseason+team_continuity+vote_stability |      0.348945 |               0.359637 |      0.348231 |   0.419339 |   0.408469 |            0.419339 |    0.709375 |             0.691635 | True                  | understat-github-mirror |     0.0883191 | True               |    -0.000713518 |               -0.0114051 |