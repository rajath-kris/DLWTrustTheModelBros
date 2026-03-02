# Mission Control + Sentinel Integration Contract (v1)

This document is the contract-first handoff for parallel development.

## Versioning Policy
- `schema_version` is required in state and quiz/capture response payloads.
- Current version: `1`.
- v1 compatibility rules:
  - add fields only (non-breaking)
  - never remove/rename required fields
  - breaking change requires new version

## Overlay -> Bridge Contract
### Endpoint
- `POST /api/v1/captures`

### Required request fields
- `capture_id`
- `timestamp_utc`
- `platform`
- `app_name`
- `window_title`
- `monitor`
- `region`
- `image_base64`

Example payload: [`fixtures/capture-request.v1.json`](/Users/mitul/Documents/GitHub/DLWTrustTheModelBros/fixtures/capture-request.v1.json)

### Required response fields
- `schema_version`
- `capture_id`
- `socratic_prompt`
- `gaps`
- `readiness_axes`

## Mission Control -> Bridge Quiz Contract
### Endpoint
- `POST /api/v1/quizzes/submit`

### Required request fields
- `topic`
- `sources`
- `answers[]` with `{question_id,user_answer}`

### Required response fields
- `schema_version`
- `quiz`
- `readiness_axes`
- `topic_updates`
- `new_gap_ids`

Example request/response: [`fixtures/quiz-submit.v1.json`](/Users/mitul/Documents/GitHub/DLWTrustTheModelBros/fixtures/quiz-submit.v1.json)

## Canonical State Contract
### Endpoint
- `GET /api/v1/state`

### Required top-level fields
- `schema_version`
- `updated_at`
- `captures`
- `gaps`
- `topics`
- `question_bank`
- `quizzes`
- `readiness_axes`

Schema source of truth: [`shared/schemas/learning-state.schema.json`](/Users/mitul/Documents/GitHub/DLWTrustTheModelBros/shared/schemas/learning-state.schema.json)

Example response: [`fixtures/state-response.v1.json`](/Users/mitul/Documents/GitHub/DLWTrustTheModelBros/fixtures/state-response.v1.json)

## Error Response Shape
All contract-level request errors must return:
```json
{
  "detail": "Human-readable reason",
  "code": "MACHINE_READABLE_CODE"
}
```

Current codes:
- `VALIDATION_ERROR`
- `INVALID_IMAGE_BASE64`
- `EMPTY_QUESTION_BANK`
- `UNKNOWN_QUESTION_ID`
- `QUESTION_SOURCE_MISMATCH`
- `QUESTION_TOPIC_MISMATCH`
- `EMPTY_QUIZ_RESULTS`
- `GAP_NOT_FOUND`

## Local Contract Validation
Run:
```bash
python scripts/validate_contract_fixtures.py
```
This validates fixtures against bridge Pydantic models and required state schema keys.
