# Error Handling

## Claude API (Anthropic)

| Scenario | Strategy | Config |
|----------|----------|--------|
| Rate limit (429) | Exponential backoff | 8 retries, base 2s |
| Overloaded (529) | Exponential backoff | 8 retries, base 2s |
| Other API error | Fail batch, continue pipeline | Skip failed batch |

The retry callback emits SSE progress events so the browser shows retry status.

If all batches fail, the pipeline returns an error message without invoking the Memory Writer.

## Gmail API

| Scenario | Strategy |
|----------|----------|
| Token expired | Auto-refresh via google-auth library |
| Refresh fails | Return unauthenticated, show login page |
| Network error | HTTP 500 to frontend |
| No credentials.json | HTTP 400 with setup instructions |

## Frontend Error Handling

| Scenario | User-Facing Behavior |
|----------|---------------------|
| Auth check fails | Show login page (fail-safe) |
| Query API error | "Something went wrong" in chat bubble |
| Build SSE error | Error message in progress indicator |
| Vault load error | Show zero counts, log to console |
| Memory detail 404 | "Error loading memory" in content viewer |
| OAuth flow fails | Error message in auth card |

## Pipeline Resilience

The build pipeline is designed to be resilient to partial failures:

1. **Batch isolation**: Each email batch is analyzed independently. If one batch fails (API error), the pipeline skips it and continues with remaining batches.
2. **Incremental processing**: Already-processed emails are tracked in `_processed_emails.json`. If the pipeline is interrupted, the next run picks up where it left off.
3. **Progress visibility**: SSE events keep the user informed during retries, failures, and batch progress.
