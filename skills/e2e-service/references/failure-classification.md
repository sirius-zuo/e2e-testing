# Failure classification

## Contents

- [Classification taxonomy](#classification-taxonomy)
- [Classification fields](#classification-fields)
- [Classification examples](#classification-examples)
- [Classification rules](#classification-rules)

## Classification taxonomy

Every verification failure must be classified into one of these categories:

| Classification | When to use |
| --- | --- |
| `product-defect` | The observed behavior diverges from a confirmed supported external boundary and the deviation originates in the product under test |
| `test-defect` | The verification logic, selector, assertion, or test data is incorrect and the product behavior matches the expected outcome |
| `environment` | The target environment is unavailable, misconfigured, or returning unexpected infrastructure errors that prevent verification |
| `inconclusive` | Evidence is insufficient to distinguish a product defect from a test or environment failure |
| `authorization-required` | The action is valid but requires explicit user or system authorization before proceeding |

## Classification fields

A classification evidence record includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `primary` | string | One of the classification taxonomy values |
| `confidence` | number | Numeric confidence between 0.0 and 1.0; must be ≥ 0.8 for `product-defect` |
| `rationale` | string | Brief explanation of the classification with evidence references |
| `evidence_ids` | array | List of evidence IDs supporting this classification |

## Classification examples

### Product defect

```json
{
  "primary": "product-defect",
  "confidence": 0.9,
  "rationale": "GET /orders/order-1 returned 404 but the route is confirmed supported and the order exists in the database. The route handler appears to be missing.",
  "evidence_ids": ["exec-get-order", "db-row-order-1"]
}
```

### Test defect

```json
{
  "primary": "test-defect",
  "confidence": 0.85,
  "rationale": "The assertion expected status 200 but the endpoint returns 201 for created resources. The test selector is wrong.",
  "evidence_ids": ["exec-post-order", "test-post-order"]
}
```

### Environment

```json
{
  "primary": "environment",
  "confidence": 0.95,
  "rationale": "Connection refused on port 43170. The gRPC server is not running in the target environment.",
  "evidence_ids": ["exec-grpc-call"]
}
```

### Inconclusive

```json
{
  "primary": "inconclusive",
  "confidence": 0.6,
  "rationale": "The response body is malformed but it is unclear whether the product or the client adapter caused the parse failure.",
  "evidence_ids": ["exec-graphql-query"]
}
```

### Authorization required

```json
{
  "primary": "authorization-required",
  "confidence": 1.0,
  "rationale": "The mutation endpoint requires production authorization. The current target tier is production and no authorization record exists.",
  "evidence_ids": ["exec-put-order"]
}
```

## Classification rules

- Every failed check must have a linked classification evidence record.
- `product-defect` classifications require confidence ≥ 0.8 and must reference
  at least one failed execution evidence ID and one artifact or diagnostic ID.
- `test-defect` classifications must reference the failing test file and line.
- `environment` classifications must reference the target tier and observed error.
- `inconclusive` classifications must identify the specific ambiguity and
  recommend the next step to resolve it.
- `authorization-required` classifications must reference the specific action
  and the approval path required to proceed.
- Classifications must not claim execution success. `read_only` evidence does
  not prove a check passed.
