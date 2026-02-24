# Config Map

## Environment Variables (.env)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENROUTER_API_KEY` | No* | — | OpenRouter API key (primary LLM provider) |
| `OPENROUTER_MODEL` | No | `moonshotai/kimi-k2.5` | Model to use via OpenRouter |
| `ANTHROPIC_API_KEY` | No* | — | Claude API key (fallback LLM provider) |

*At least one of `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` must be set.

## Config Settings (config/settings.py)

### File Paths

| Setting | Default | Purpose |
|---------|---------|---------|
| `PROJECT_ROOT` | Auto-detected | Top-level project directory |
| `VAULT_ROOT` | `PROJECT_ROOT/vault` | Memory vault storage |
| `CONFIG_DIR` | `PROJECT_ROOT/config` | Configuration directory |
| `CREDENTIALS_PATH` | `CONFIG_DIR/credentials.json` | Google OAuth credentials |
| `TOKEN_PATH` | `CONFIG_DIR/token file` | Saved Gmail auth token |

### LLM Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `OPENROUTER_API_KEY` | From env var | OpenRouter API key (primary) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `OPENROUTER_MODEL` | `moonshotai/kimi-k2.5` | Model ID on OpenRouter |
| `ANTHROPIC_API_KEY` | From env var | Anthropic API key (fallback) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model ID |
| `MAX_TOKENS` | `4096` | Max response length per API call |

### Gmail Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `GMAIL_SCOPES` | `gmail.readonly` | OAuth permission scope |
| `DEFAULT_MAX_EMAILS` | `500` | Max emails to fetch per build |
| `DEFAULT_DAYS_BACK` | `180` | How far back to look for emails |
| `EMAIL_BATCH_SIZE` | `10` | Emails per analysis batch |

### Retry Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `API_MAX_RETRIES` | `8` | Max retries per API call |
| `API_RETRY_BASE_DELAY` | `2.0` | Base delay (seconds), doubles each retry |

### Memory Types

| Setting | Default | Purpose |
|---------|---------|---------|
| `MEMORY_TYPES` | `['decisions', 'people', 'commitments', 'action_required']` | Valid vault categories |

## Frontend Defaults (index.html)

| Setting | Default | Purpose |
|---------|---------|---------|
| `buildDays` input | `180` | Days back for manual build |
| `buildMax` input | `500` | Max emails for manual build |
| Auto-build URL | `days_back=180&max_emails=500` | Incremental build on login |
