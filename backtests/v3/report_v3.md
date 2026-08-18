# V3 feature ablation

Families are accepted only on training folds; 2025/26 is never used for selection.

Final families: **vote_stability**
V3 Spearman: **0.353**
V1: **0.363**
Persistence: **0.360**
Lift vs V1: **-0.010**
Lift vs persistence: **-0.007**

| prior_season   | target_season   |   training_folds |   evaluated_players | selected_families   |   v1_spearman |   persistence_spearman |   v3_spearman |   v3_top20 |   v1_top20 |   persistence_top20 |   v3_ndcg50 |   persistence_ndcg50 | understat_available   | is_final_holdout   |   v3_lift_vs_v1 |   v3_lift_vs_persistence |
|:---------------|:----------------|-----------------:|--------------------:|:--------------------|--------------:|-----------------------:|--------------:|-----------:|-----------:|--------------------:|------------:|---------------------:|:----------------------|:-------------------|----------------:|-------------------------:|
| 2021-22        | 2022-23         |                2 |                 342 | none                |      0.429079 |               0.429068 |      0.403492 |   0.326348 |   0.326348 |            0.326348 |    0.636902 |             0.70991  | False                 | False              |      -0.0255866 |              -0.0255763  |
| 2022-23        | 2023-24         |                3 |                 323 | multiseason         |      0.417709 |               0.423078 |      0.39445  |   0.447619 |   0.42381  |            0.385714 |    0.697464 |             0.717479 | False                 | False              |      -0.0232597 |              -0.0286286  |
| 2023-24        | 2024-25         |                4 |                 339 | none                |      0.38976  |               0.390683 |      0.371862 |   0.419797 |   0.419797 |            0.419797 |    0.73609  |             0.739561 | False                 | False              |      -0.0178984 |              -0.0188208  |
| 2024-25        | 2025-26         |                5 |                 351 | vote_stability      |      0.362601 |               0.359637 |      0.35251  |   0.427619 |   0.427619 |            0.41836  |    0.668473 |             0.691451 | False                 | True               |      -0.0100909 |              -0.00712646 |