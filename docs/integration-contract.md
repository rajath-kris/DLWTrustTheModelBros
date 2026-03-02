# Integration Contract (v1)

## Versioning policy
- `schema_version` is currently fixed to `1`.
- v1 is additive-only: new optional fields may be added without breaking existing consumers.
- Any breaking contract change requires a new schema version.

## Standard API error shape
All API errors use:

```json
{ "detail": "...", "code": "MACHINE_READABLE_CODE" }
```

Supported codes:
- `VALIDATION_ERROR`
- `INVALID_IMAGE_BASE64`
- `EMPTY_QUESTION_BANK`
- `UNKNOWN_QUESTION_ID`
- `QUESTION_SOURCE_MISMATCH`
- `QUESTION_TOPIC_MISMATCH`
- `EMPTY_QUIZ_RESULTS`
- `GAP_NOT_FOUND`

## Capture contract
### Request
`POST /api/v1/captures` request body follows `CaptureRequest`.
Reference fixture: `fixtures/capture-request.v1.json`.

### Response
Capture response includes:
- `schema_version`
- `capture_id`
- `thread_id`
- `turn_index`
- `socratic_prompt`
- `gaps`
- `readiness_axes`

## Quiz submit contract
### Request
`POST /api/v1/quizzes/submit`

```json
{
  "topic": "Dynamic Programming",
  "sources": ["tutorial"],
  "answers": [
    { "question_id": "qb-dp-01", "user_answer": "Define states and valid transitions" }
  ]
}
```

### Response
Quiz submit response includes:
- `schema_version`
- `quiz`
- `readiness_axes`
- `topic_updates`
- `new_gap_ids`

## Canonical state contract
`GET /api/v1/state` returns `LearningState` with required top-level keys:
- `schema_version`
- `updated_at`
- `captures`
- `gaps`
- `topics`
- `question_bank`
- `quizzes`
- `readiness_axes`

Reference fixture: `fixtures/state-response.v1.json`.

## Fixture validation
Run:

```bash
cd /Users/mitul/Documents/GitHub/DLWTrustTheModelBros
python scripts/validate_contract_fixtures.py
```

Validation checks:
- Pydantic validation against backend models (`CaptureRequest`, `LearningState`, `QuizSubmitRequest`)
- Required key presence from `shared/schemas/learning-state.schema.json`
