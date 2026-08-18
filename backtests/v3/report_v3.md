# V3 feature ablation

Families are accepted only on training folds; 2025/26 is never used for selection.

Final families: **xg_regression**
V3 Spearman: **0.360**
V1: **0.366**
Persistence: **0.360**
Lift vs V1: **-0.007**
Lift vs persistence: **-0.000**

| prior_season   | target_season   |   training_folds |   evaluated_players | selected_families   |   v1_spearman |   persistence_spearman |   v3_spearman |   v3_top20 |   v1_top20 |   persistence_top20 |   v3_ndcg50 |   persistence_ndcg50 | understat_available   | is_final_holdout   |   v3_lift_vs_v1 |   v3_lift_vs_persistence |
|:---------------|:----------------|-----------------:|--------------------:|:--------------------|--------------:|-----------------------:|--------------:|-----------:|-----------:|--------------------:|------------:|---------------------:|:----------------------|:-------------------|----------------:|-------------------------:|
| 2021-22        | 2022-23         |                2 |                 342 | xg_regression       |      0.436558 |               0.429068 |      0.412611 |   0.341973 |   0.337218 |            0.326348 |    0.68171  |             0.70991  | True                  | False              |     -0.023947   |             -0.0164571   |
| 2022-23        | 2023-24         |                3 |                 323 | none                |      0.41595  |               0.423078 |      0.391726 |   0.395714 |   0.395714 |            0.385714 |    0.697892 |             0.717479 | True                  | False              |     -0.0242242  |             -0.0313519   |
| 2023-24        | 2024-25         |                4 |                 339 | multiseason         |      0.377237 |               0.390683 |      0.366451 |   0.393728 |   0.419797 |            0.419797 |    0.693034 |             0.739561 | True                  | False              |     -0.0107862  |             -0.0242321   |
| 2024-25        | 2025-26         |                5 |                 351 | xg_regression       |      0.366373 |               0.359637 |      0.359518 |   0.409101 |   0.41836  |            0.41836  |    0.701654 |             0.691591 | True                  | True               |     -0.00685533 |             -0.000118932 |