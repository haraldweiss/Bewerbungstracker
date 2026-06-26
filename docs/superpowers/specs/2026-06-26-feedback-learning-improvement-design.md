# Feedback-Learning Improvement Design

## Context

The job-matching pipeline already stores user feedback on `JobMatch` rows and
uses it in two places:

- `services/job_matching/learner.py` builds per-user centroids for imported and
  dismissed jobs, then adjusts prefilter scores via cosine similarity.
- `services/job_matching/feedback_context.py` injects recent feedback into the
  AI match prompt.

Production data shows this is active for the main user, but the sample balance
is skewed: many more dismissed samples than imported samples. Feedback reasons
are counted and displayed, but they do not yet drive much deterministic scoring
behavior.

## Goals

1. Make adaptive score adjustment more stable when dismissed samples massively
   outnumber imported samples.
2. Use structured feedback reasons as concrete signals, not just counters.
3. Ensure common feedback paths update the learning profile consistently.
4. Keep changes privacy-preserving: no raw CV, email body, or full job text in
   logs.

## Non-Goals

- No database migration unless tests prove existing columns are insufficient.
- No replacement of the current embedding model or Ollama dependency.
- No LLM retraining.
- No production deploy in the implementation step unless requested separately.

## Proposed Behavior

### Balanced Centroid Influence

`compute_score_adjustment()` will keep the existing imported-vs-dismissed
centroid model, but reduce overreaction from highly imbalanced sample counts.
The adjustment remains bounded by `user.job_learn_weight_pct`, but the
dismissed-side penalty is scaled down when dismissed samples greatly exceed
imported samples.

This preserves the useful signal that rejected jobs matter while avoiding a
profile that becomes broadly pessimistic after many dismisses.

### Reason-Specific Deterministic Adjustments

Add a small helper in `learner.py` that reads `profile.reason_counts` and applies
bounded penalties for strong repeated reasons:

- `wrong_location`: penalize jobs whose location text does not overlap the
  user's existing positive/imported locations when enough location feedback
  exists.
- `wrong_seniority`: penalize obvious seniority mismatch terms in title or
  description.
- `missing_skills`: modestly increase the penalty from the existing CV-token
  mismatch by reducing the final adjusted score when this reason dominates.
- `salary_too_low`: no deterministic penalty unless salary fields become
  available; keep it counted and prompt-visible only.

The first implementation should be intentionally conservative: small caps,
clear tests, and no hard dismisses from reason logic alone.

### Learning Path Consistency

Currently direct import and PATCH dismissal update centroids. The implementation
will close obvious gaps:

- Quick-action dismissal should call `update_centroid_for_feedback()` after it
  sets `status='dismissed'`.
- Bulk dismissal should update the learner for each affected match when
  embeddings exist.
- System auto-dismisses from cron should not automatically train as user
  preference unless they carry a user-originated feedback signal.

### Observability

Add debug-level logging for aggregate score adjustments only:

- match id
- base score
- adjusted score
- reason tags that contributed

Do not log CV text, job descriptions, feedback text, or email content.

## Testing Plan

Use TDD with focused tests:

1. `compute_score_adjustment()` remains unchanged when learning is disabled,
   profile is cold, or embeddings are missing.
2. Imbalanced dismissed samples do not overwhelm imported similarity.
3. Repeated `wrong_seniority` feedback applies a bounded penalty to matching
   seniority terms.
4. Quick-action dismissal updates `UserLearnProfile` when an embedding exists.
5. Bulk dismissal updates `UserLearnProfile` for embedded matches.
6. Existing learner and prefilter tests continue passing.

## Rollout Notes

This is a code-only change. After merge, existing profile data should start
using the refined scoring immediately. No backfill is required, because
`reason_counts`, centroids, and embeddings already exist.

Before production deploy, run at minimum:

```bash
pytest tests/services/test_learner.py tests/services/test_prefilter_learner.py tests/api/test_jobs_user.py tests/integration/test_learning_e2e.py
```

If changing cron behavior, also run:

```bash
pytest tests/api/test_jobs_cron.py
```
