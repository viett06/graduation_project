# Saving Plan API Test Cases

Base URL:

```text
{{base_url}}/api/v1/saving-plan
```

Default headers for protected endpoints:

```http
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

Notes for frontend:

- `POST /optimize`, `POST /plan-by-term`, and `POST /{user_id}/save` require login.
- In `POST /{user_id}/save`, backend currently ignores the path `user_id` and uses `user_id` from the access token.
- `GET /history/{user_id}`, `GET /{user_id}`, `GET /{user_id}/{plan_id}`, and `DELETE /{user_id}/{plan_id}` currently do not require auth in the controller.
- `algorithm_used` returned by backend is fixed as `dp`.
- There is no monthly extra deposit, extra schedule, withdrawal schedule, or algorithm selection in request bodies.

## 1. Optimize Saving Plan

Use this when the frontend wants backend to run DP optimization and return best/top saving plans.

```http
POST {{base_url}}/api/v1/saving-plan/optimize
```

Request body:

```json
{
  "name": "Ke hoach tiet kiem 12 thang",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106000000,
  "prefer_rate": "ONLINE",
  "codes": ["VCB", "TCB", "MB"],
  "notes": "Frontend test optimize"
}
```

Required fields:

- `name`: string
- `duration_month`: number
- `total_amount`: number
- `goal_amount`: number

Optional fields:

- `prefer_rate`: `"ONLINE"` or `"COUNTER"`, default `"ONLINE"`
- `codes`: array of bank codes, default `[]`
- `notes`: string or null

Expected 200 response shape:

```json
{
  "plan_id": null,
  "final_amount": 106500000,
  "achieved_interest": 6500000,
  "is_goal_met": true,
  "plan_details": {
    "best_plan": {
      "rank": 1,
      "final_amount": 106500000,
      "interest_earned": 6500000,
      "interest_rate_effective_pct": 6.5,
      "banks_used": ["Example Bank"],
      "total_transfer_fees": 0,
      "summary": {
        "initial_amount": 100000000,
        "net_contribution": 100000000
      },
      "steps": [
        {
          "month": 0,
          "action": "initial",
          "amount": 100000000,
          "note": "So tien ban dau: 100,000,000 VND"
        },
        {
          "month": 1,
          "action": "open_book",
          "amount": 100000000,
          "term_months": 12,
          "bank_id": "VCB",
          "bank_name": "Example Bank",
          "annual_rate_pct": 6.5,
          "note": "Ky han 12T"
        }
      ]
    },
    "top_plans": [],
    "selection_mode": "fallback_top_highest",
    "single_deposit_benchmark": null
  },
  "top_plans": [],
  "algorithm_used": "dp",
  "probability_success": null
}
```

Expected 400 response shape:

```json
{
  "detail": "error message"
}
```

Frontend mapping:

- Show `final_amount`, `achieved_interest`, `is_goal_met`.
- Use `plan_details.best_plan.steps` to render timeline.
- Use `top_plans` to render alternative plans.
- Send selected plan to `POST /{user_id}/save` using `plan_data`.

## 2. Create Fixed Term Plan By Highest Rate

Use this when the user manually selects a term and wants to deposit all money into the bank with the highest rate for that term. This endpoint does not optimize.

```http
POST {{base_url}}/api/v1/saving-plan/plan-by-term
```

Request body:

```json
{
  "total_amount": 100000000,
  "term_month": 12,
  "channel": "ONLINE"
}
```

Required fields:

- `total_amount`: number
- `term_month`: number

Optional fields:

- `channel`: `"ONLINE"`, `"COUNTER"`, or null. If null, backend checks all channels.

Expected 200 response shape:

```json
{
  "plan_id": null,
  "bank_id": 1,
  "bank_code": "VCB",
  "bank_name": "Example Bank",
  "term_month": 12,
  "channel": "ONLINE",
  "annual_rate_pct": 6.5,
  "total_amount": 100000000,
  "achieved_interest": 6500000,
  "final_amount": 106500000,
  "plan_details": {
    "strategy": "fixed_term_highest_rate",
    "summary": {
      "initial_amount": 100000000,
      "term_month": 12,
      "annual_rate_pct": 6.5,
      "interest_earned": 6500000,
      "final_amount": 106500000
    },
    "steps": [
      {
        "month": 0,
        "action": "initial",
        "amount": 100000000,
        "note": "So tien ban dau: 100,000,000 VND"
      },
      {
        "month": 1,
        "action": "open_book",
        "amount": 100000000,
        "term_months": 12,
        "bank_id": "VCB",
        "bank_name": "Example Bank",
        "annual_rate_pct": 6.5,
        "channel": "ONLINE",
        "note": "Gui toan bo so tien vao Example Bank ky han 12 thang voi lai suat 6.50%/nam"
      },
      {
        "month": 13,
        "action": "mature",
        "amount": 106500000,
        "term_months": 12,
        "bank_id": "VCB",
        "bank_name": "Example Bank",
        "annual_rate_pct": 6.5,
        "channel": "ONLINE",
        "note": "Dao han: goc 100,000,000 + lai 6,500,000 VND"
      }
    ]
  }
}
```

Expected 400 response shape:

```json
{
  "detail": "Khong tim thay lai suat phu hop voi ky han va so tien da chon."
}
```

Frontend mapping:

- Use `bank_name`, `bank_code`, `annual_rate_pct`, `achieved_interest`, `final_amount` for summary card.
- Use `plan_details.steps` to render timeline.
- Use this response as `plan_data` when saving the selected plan.

## 3. Save Selected Plan

Use this after user selects a plan from `/optimize` or `/plan-by-term`.

```http
POST {{base_url}}/api/v1/saving-plan/{{user_id}}/save
```

Request body for optimized plan:

```json
{
  "name": "Ke hoach toi uu DP",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106000000,
  "notes": "User selected best DP plan",
  "plan_data": {
    "best_plan": {
      "rank": 1,
      "final_amount": 106500000,
      "interest_earned": 6500000,
      "steps": []
    }
  }
}
```

Request body for fixed term plan:

```json
{
  "name": "Gui ky han 12 thang lai cao nhat",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106500000,
  "notes": "User selected fixed term plan",
  "plan_data": {
    "strategy": "fixed_term_highest_rate",
    "summary": {
      "initial_amount": 100000000,
      "term_month": 12,
      "annual_rate_pct": 6.5,
      "interest_earned": 6500000,
      "final_amount": 106500000
    },
    "steps": []
  }
}
```

Required fields:

- `name`: string
- `duration_month`: number
- `total_amount`: number
- `goal_amount`: number
- `plan_data`: object

Optional fields:

- `notes`: string or null

Expected 200 response shape:

```json
{
  "id": 10,
  "name": "Gui ky han 12 thang lai cao nhat",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106500000,
  "notes": "User selected fixed term plan",
  "is_active": true,
  "created_at": "2026-06-03T10:00:00Z",
  "algorithm_used": "dp",
  "plan_data": {
    "strategy": "fixed_term_highest_rate",
    "summary": {}
  }
}
```

Expected 400 response shape:

```json
{
  "detail": "error message"
}
```

Frontend mapping:

- Store returned `id` as `plan_id`.
- `algorithm_used` is backend metadata, not a frontend input.
- Use `plan_data` to render saved detail without recalculating.

## 4. Get Saving Plan History

Use this to list active plans for a user.

```http
GET {{base_url}}/api/v1/saving-plan/history/{{user_id}}
```

Path params:

- `user_id`: number

Expected 200 response shape:

```json
[
  {
    "id": 10,
    "name": "Gui ky han 12 thang lai cao nhat",
    "duration_month": 12,
    "total_amount": 100000000,
    "goal_amount": 106500000,
    "notes": "User selected fixed term plan",
    "is_active": true,
    "created_at": "2026-06-03T10:00:00Z",
    "algorithm_used": "dp",
    "plan_data": {
      "strategy": "fixed_term_highest_rate",
      "summary": {}
    }
  }
]
```

Frontend mapping:

- Use for history screen.
- Sort is already newest first from backend.

## 5. Get Active Saving Plans

This returns the same active plan list as `/history/{user_id}`.

```http
GET {{base_url}}/api/v1/saving-plan/{{user_id}}
```

Path params:

- `user_id`: number

Expected 200 response shape:

```json
[
  {
    "id": 10,
    "name": "Gui ky han 12 thang lai cao nhat",
    "duration_month": 12,
    "total_amount": 100000000,
    "goal_amount": 106500000,
    "notes": "User selected fixed term plan",
    "is_active": true,
    "created_at": "2026-06-03T10:00:00Z",
    "algorithm_used": "dp",
    "plan_data": {}
  }
]
```

Frontend mapping:

- Prefer `/history/{user_id}` for clarity.
- This endpoint is functionally duplicate with history in current controller.

## 6. Get Saving Plan Detail

Use this to open one saved plan.

```http
GET {{base_url}}/api/v1/saving-plan/{{user_id}}/{{plan_id}}
```

Path params:

- `user_id`: number
- `plan_id`: number

Expected 200 response shape:

```json
{
  "id": 10,
  "name": "Gui ky han 12 thang lai cao nhat",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106500000,
  "notes": "User selected fixed term plan",
  "is_active": true,
  "created_at": "2026-06-03T10:00:00Z",
  "algorithm_used": "dp",
  "plan_data": {
    "strategy": "fixed_term_highest_rate",
    "summary": {},
    "steps": []
  }
}
```

Expected 404 response shape:

```json
{
  "detail": "Saving plan not found"
}
```

Frontend mapping:

- Use `plan_data.steps` for detail timeline.
- Use top-level fields for title and saved metadata.

## 7. Delete Saving Plan

This is a soft delete. Backend sets `is_active=false`.

```http
DELETE {{base_url}}/api/v1/saving-plan/{{user_id}}/{{plan_id}}
```

Path params:

- `user_id`: number
- `plan_id`: number

Expected 200 response shape:

```json
{
  "id": 10,
  "is_active": false,
  "message": "Saving plan deleted successfully"
}
```

Expected 404 response shape:

```json
{
  "detail": "Saving plan not found"
}
```

Frontend mapping:

- After success, remove item from local list or refetch `/history/{user_id}`.

## Frontend Endpoint Map

```ts
export const savingPlanApi = {
  optimize: "POST /api/v1/saving-plan/optimize",
  planByTerm: "POST /api/v1/saving-plan/plan-by-term",
  save: "POST /api/v1/saving-plan/{user_id}/save",
  history: "GET /api/v1/saving-plan/history/{user_id}",
  list: "GET /api/v1/saving-plan/{user_id}",
  detail: "GET /api/v1/saving-plan/{user_id}/{plan_id}",
  delete: "DELETE /api/v1/saving-plan/{user_id}/{plan_id}"
};
```

## Suggested Manual Test Order

1. Login and store `access_token`.
2. Call `POST /optimize`.
3. Save one optimized plan with `POST /{user_id}/save`.
4. Call `POST /plan-by-term`.
5. Save fixed term plan with `POST /{user_id}/save`.
6. Call `GET /history/{user_id}`.
7. Call `GET /{user_id}/{plan_id}`.
8. Call `DELETE /{user_id}/{plan_id}`.
9. Call `GET /history/{user_id}` again and confirm deleted plan is gone.

