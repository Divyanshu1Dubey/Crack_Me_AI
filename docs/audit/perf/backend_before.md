# Backend perf probe: before

Generated 2026-11-01T23:46:52 on `crack_local` (PostgreSQL 16.15, 127.0.0.1), auth `supabase`, runs 10, rtt 0.0 ms/statement, GoTrue 0.0 ms/miss. Queries = statements executed incl. SAVEPOINT/RELEASE; dup = repeated executions of one statement template; times in ms (p50/p95 over the runs).

| endpoint | user | status | q cold | q warm | writes | dup | SQL ms | wall cold p50/p95 | wall warm p50/p95 | KB gz |
|---|---|---|---|---|---|---|---|---|---|---|
| `GET /api/auth/profile/` | student | 200 | 17 | 17 | 0 | 6 | 3.62 | 13.4/20.1 | 13.2/14.1 | 0.4 |
| `GET /api/auth/profile/` | premium | 200 | 14 | 14 | 0 | 5 | 3.02 | 12.4/41.5 | 11.8/12.9 | 0.5 |
| `GET /api/auth/tokens/` | student | 200 | 13 | 13 | 0 | 4 | 2.7 | 9.3/12.3 | 9.1/10.5 | 0.1 |
| `GET /api/auth/tokens/` | premium | 200 | 13 | 13 | 0 | 4 | 2.79 | 9.1/10.2 | 9.3/10.6 | 0.1 |
| `GET /api/analytics/announcements/` | student | 200 | 6 | 6 | 0 | 0 | 1.71 | 6.9/7.3 | 7.0/7.6 | 0.0 |
| `GET /api/analytics/dashboard/bundle/` | student | 200 | 16 | 4 | 0 | 0 | 1.02 | 26.6/31.6 | 4.5/5.1 | 0.4 |
| `GET /api/analytics/dashboard/bundle/` | premium | 200 | 16 | 4 | 0 | 0 | 1.1 | 27.5/32.4 | 4.7/5.6 | 0.4 |
| `GET /api/questions/stats/?exam_source=UPSC%20CMS` | student | 200 | 13 | 13 | 0 | 0 | 13.2 | 27.1/31.6 | 23.6/25.7 | 0.5 |
| `GET /api/questions/?page=1&page_size=20&exam_type=cms` | student | 200 | 13 | 5 | 0 | 0 | 1.36 | 66.8/75.3 | 6.1/6.5 | 5.0 |
| `GET /api/questions/?page=1&page_size=20&exam_type=cms` | premium | 200 | 13 | 5 | 0 | 0 | 1.34 | 41.1/47.4 | 6.1/7.0 | 4.5 |
| `GET /api/questions/?page=1&page_size=20&exam_type=cms` | admin | 200 | 10 | 10 | 0 | 0 | 24.3 | 60.8/80.8 | 61.6/96.0 | 12.1 |
| `GET /api/questions/?page=1&page_size=20&exam_type=cms&search=anaemia` | student | 200 | 16 | 5 | 0 | 0 | 1.34 | 1231.6/1309.8 | 6.0/7.2 | 15.3 |
| `GET /api/questions/subjects/` | student | 200 | 5 | 5 | 0 | 0 | 12.02 | 16.9/20.5 | 18.8/24.7 | 0.7 |
| `GET /api/questions/topics/` | student | 200 | 5 | 5 | 0 | 0 | 10.86 | 82.0/141.6 | 80.8/152.3 | 38.4 |
| `GET /api/questions/years/?exam_type=cms` | student | 200 | 5 | 5 | 0 | 0 | 2.91 | 6.8/8.5 | 6.8/8.9 | 0.0 |
| `GET /api/questions/{q_img}/` | anon | 200 | 10 | 10 | 0 | 0 | 8.42 | 24.5/28.4 | 24.2/25.7 | 1.1 |
| `GET /api/questions/{q_show}/` | student | 200 | 18 | 18 | 0 | 1 | 10.71 | 29.8/34.0 | 31.4/33.2 | 2.9 |
| `GET /api/questions/{q_img}/` | premium | 200 | 17 | 17 | 0 | 1 | 9.87 | 29.6/31.8 | 29.7/34.2 | 1.2 |
| `GET /api/questions/{q_img}/` | admin | 200 | 14 | 14 | 0 | 1 | 8.79 | 25.0/31.1 | 25.6/28.0 | 1.2 |
| `GET /api/questions/{q_neet}/` | premium | 200 | 17 | 17 | 0 | 1 | 12.34 | 39.2/192.3 | 43.1/50.2 | 8.4 |
| `GET /api/questions/{q_show}/similar/` | student | 200 | 21 | 21 | 0 | 2 | 13.73 | 41.8/47.8 | 40.6/69.0 | 2.4 |
| `GET /api/questions/{q_img}/similar/` | premium | 200 | 19 | 19 | 0 | 2 | 12.67 | 38.9/42.0 | 37.6/41.8 | 2.6 |
| `GET /api/questions/discussions/?question={q_img}` | premium | 200 | 6 | 6 | 0 | 0 | 1.71 | 8.8/10.0 | 9.0/10.6 | 0.1 |
| `GET /api/questions/{q_img}/ai/why_correct/` | premium | 200 | 12 | 12 | 0 | 0 | 6.07 | 18.3/21.4 | 18.3/19.4 | 0.0 |
| `GET /api/questions/{q_img}/ai/clinical/` | premium | 200 | 12 | 12 | 0 | 0 | 6.92 | 19.0/21.9 | 19.8/23.6 | 0.0 |
| `GET /api/questions/{q_img}/ai/mnemonic/` | premium | 200 | 12 | 12 | 0 | 0 | 6.09 | 21.8/39.5 | 18.3/19.5 | 0.0 |
| `GET /api/questions/{q_img}/ai/exam_importance/` | premium | 200 | 11 | 11 | 0 | 0 | 5.76 | 16.6/18.8 | 17.4/19.2 | 0.0 |
| `GET /api/questions/{q_img}/ai/concept/` | premium | 200 | 12 | 12 | 0 | 0 | 6.38 | 19.8/24.9 | 19.3/23.4 | 0.0 |
| `GET /api/questions/{q_img}/ai/why_incorrect/` | premium | 200 | 12 | 12 | 0 | 0 | 5.82 | 17.9/19.8 | 17.3/21.0 | 0.0 |
| `GET /api/questions/{q_img}/ai/related_pyqs/` | premium | 200 | 13 | 13 | 0 | 0 | 7.22 | 44.5/52.6 | 20.4/27.1 | 5.5 |
| `GET /api/questions/{q_img}/ai/related_topics/` | premium | 200 | 12 | 11 | 0 | 0 | 6.11 | 25.4/28.1 | 18.4/21.0 | 0.2 |
| `POST /api/questions/{q_img}/attempt/` | premium | 200 | 40 | 40 | 9 | 0 | 13.87 | 29.8/205.2 | 37.7/51.1 | 0.2 |
| `POST /api/questions/{q_show}/attempt/` | student | 200 | 37 | 37 | 8 | 1 | 14.82 | 41.5/48.5 | 39.0/43.8 | 0.4 |
| `POST /api/questions/{q_img}/practice/attempt/` | premium | 200 | 48 | 48 | 12 | 1 | 14.3 | 41.9/67.6 | 37.6/41.7 | 0.2 |
| `GET /api/questions/practice_queue/?mode=random` | student | 200 | 8 | 9 | 0 | 0 | 15.93 | 30.0/77.6 | 31.2/42.2 | 0.1 |
| `GET /api/questions/recall_search/?q=hypertension` | anon | 200 | 16 | 0 | 0 | 0 | 0.0 | 1702.2/1807.8 | 2.8/3.7 | 5.0 |
| `GET /api/questions/recall_search/?q=hypertension` | student | 200 | 22 | 5 | 0 | 0 | 1.35 | 1451.1/1731.2 | 5.5/6.2 | 1.0 |
| `GET /api/questions/recall_search/?q=hypertension` | premium | 200 | 18 | 5 | 0 | 0 | 1.31 | 250.5/280.2 | 6.2/7.0 | 5.6 |
| `GET /api/tests/?scope=library` | student | 200 | 7 | 7 | 0 | 0 | 61.92 | 73.1/89.5 | 73.9/97.5 | 1.8 |
| `POST /api/tests/{paper}/start/` | premium | 200 | 16 | 16 | 1 | 2 | 16.7 | 77.4/182.4 | 85.6/114.0 | 21.1 |
| `POST /api/tests/{paper}/submit/` | premium | 200 | 906 | 906 | 283 | 543 | 169.91 | 450.8/496.1 | 445.5/639.9 | 0.2 |
| `GET /api/tests/{paper}/review/?attempt_id={attempt}` | premium | 200 | 7 | 7 | 0 | 0 | 5.18 | 24.5/40.8 | 21.7/28.4 | 50.6 |
| `POST /api/tests/{test20}/start/` | student | 200 | 15 | 15 | 1 | 1 | 10.07 | 36.0/39.9 | 37.7/41.0 | 4.9 |
| `POST /api/tests/{test20}/submit/` | student | 200 | 182 | 182 | 56 | 90 | 42.12 | 103.3/264.4 | 105.6/108.9 | 0.2 |
| `GET /api/analytics/weak-topics/` | premium | 200 | 6 | 6 | 0 | 0 | 2.37 | 8.6/15.2 | 8.8/10.1 | 0.1 |
| `GET /api/analytics/topic-performance/` | premium | 200 | 5 | 5 | 0 | 0 | 1.78 | 6.6/8.7 | 6.6/10.7 | 0.0 |
| `GET /api/analytics/performance-trend/` | premium | 200 | 5 | 5 | 0 | 0 | 1.74 | 6.8/9.1 | 7.0/11.5 | 0.2 |
| `GET /api/analytics/score-prediction/` | premium | 200 | 8 | 8 | 0 | 0 | 2.67 | 9.4/10.8 | 9.2/12.8 | 0.2 |
| `GET /api/analytics/heatmap/` | premium | 200 | 5 | 5 | 0 | 0 | 1.31 | 5.8/11.3 | 5.5/15.0 | 0.1 |
| `GET /api/analytics/leaderboard/` | premium | 200 | 20 | 4 | 0 | 0 | 1.08 | 21.0/24.9 | 4.6/6.2 | 0.3 |
| `GET /api/analytics/dashboard_v3/` | premium | 200 | 8 | 4 | 0 | 0 | 1.17 | 25.0/32.1 | 5.2/6.6 | 0.4 |
| `GET /api/analytics/dashboard/` | premium | 200 | 9 | 4 | 0 | 0 | 1.02 | 10.2/14.9 | 4.4/44.5 | 0.2 |
| `POST /api/ai/tutor/` | premium | 200 | 6 | 6 | 0 | 0 | 33.07 | 86.8/91.2 | 85.5/92.1 | 0.6 |

## Flows (critical path: stages in sequence, a stage's requests in parallel)

| flow | phase | requests | total queries | critical-path queries | critical-path ms |
|---|---|---|---|---|---|
| dashboard (student) | warm | 5 | 53 | 30 | 36.8 |
| bank question open (premium) | warm | 3 | 42 | 19 | 37.6 |
| practice answer + reveal (premium) | warm | 9 | 135 | 53 | 58.1 |
| test submit + review, 120 questions (premium) | warm | 2 | 913 | 913 | 467.2 |
| dashboard (student) | cold | 5 | 65 | 33 | 40.5 |
| bank question open (premium) | cold | 3 | 42 | 19 | 38.9 |
| practice answer + reveal (premium) | cold | 9 | 136 | 53 | 74.3 |
| test submit + review, 120 questions (premium) | cold | 2 | 913 | 913 | 475.3 |

## Boot work

* `relink_fixture_images_dry_run_ms`: 1259.9
* `relink_fixture_images_statements`: 2

## Repeated statements (top duplicate templates, warm)

* `auth.profile` (student): 4x `SELECT %s AS "a" FROM "accounts_subscription" WHERE ("accounts_subscription"."status" = %s AND "accounts_subscription"."`; 3x `SELECT "accounts_tokenconfig"."id", "accounts_tokenconfig"."free_daily_tokens", "accounts_tokenconfig"."free_weekly_toke`
* `auth.profile` (premium): 4x `SELECT %s AS "a" FROM "accounts_subscription" WHERE ("accounts_subscription"."status" = %s AND "accounts_subscription"."`
* `auth.tokens` (student): 4x `SELECT "accounts_tokenconfig"."id", "accounts_tokenconfig"."free_daily_tokens", "accounts_tokenconfig"."free_weekly_toke`
* `auth.tokens` (premium): 4x `SELECT "accounts_tokenconfig"."id", "accounts_tokenconfig"."free_daily_tokens", "accounts_tokenconfig"."free_weekly_toke`
* `tests.start` (premium): 3x `SELECT %s AS "a" FROM "accounts_subscription" WHERE ("accounts_subscription"."status" = %s AND "accounts_subscription"."`
* `tests.submit` (premium): 113x `INSERT INTO "analytics_usertopicperformance" ("user_id", "topic_id", "subject_id", "total_attempts", "correct_answers", `; 113x `UPDATE "analytics_usertopicperformance" SET "total_attempts" = ("analytics_usertopicperformance"."total_attempts" + %s),`; 111x `SELECT "analytics_usertopicperformance"."id" AS "pk" FROM "analytics_usertopicperformance" WHERE ("analytics_usertopicpe` <!-- pragma: allowlist secret: SQL statement templates with %s placeholders, no data -->
* `tests.submit` (student): 22x `UPDATE "analytics_usertopicperformance" SET "total_attempts" = ("analytics_usertopicperformance"."total_attempts" + %s),`; 20x `SELECT "analytics_usertopicperformance"."id" AS "pk" FROM "analytics_usertopicperformance" WHERE ("analytics_usertopicpe`; 18x `INSERT INTO "analytics_usertopicperformance" ("user_id", "topic_id", "subject_id", "total_attempts", "correct_answers", ` <!-- pragma: allowlist secret: SQL statement templates with %s placeholders, no data -->
