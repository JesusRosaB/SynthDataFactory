# AI Assistant - Schema Generator

[Spanish](AI_ASSISTANT.md) | [English](AI_ASSISTANT.en.md)

SynthDataFactory AI Assistant uses **GROQ** with model **llama-3.3-70b-versatile** to generate data schemas and suggest sink configuration from natural language descriptions.

## Setup

### 1. Get a GROQ API Key

1. Go to [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign in
3. Create an API key
4. Copy the key

### 2. Configure Environment Variable

Option A (`.env`, recommended):

```bash
cp .env.example .env
```

Then set:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Option B (system env var):

```bash
export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Restart containers

```bash
docker-compose down
docker-compose up -d
```

## How To Use

1. Open `http://localhost`
2. Log in or register from the top bar
3. Click **AI Assistant**
4. Describe your dataset
5. Click **Generate Schema**
6. Review generated fields and suggested sink, then adjust if needed

## AI Sink Suggestions

Assistant responses may include:
- `suggested_target_type`: `file`, `mqtt`, `kafka`, `http`, `rabbitmq`, `postgres`, `mongodb`, `mysql`
- `suggested_sink_config`: recommended settings for that target

If context is not specific enough, AI usually defaults to `file` + `json`.

Expected response shape (summary):

```json
{
  "simulation_name": "name",
  "suggested_records": 1000,
  "suggested_target_type": "postgres",
  "suggested_sink_config": {
    "postgres_host": "localhost",
    "postgres_port": 5432,
    "postgres_db": "synthdata",
    "postgres_user": "postgres",
    "postgres_table": "synthetic_data"
  },
  "schema_fields": []
}
```

## Supported Field Types

| Type | Description | Parameters |
|---|---|---|
| `int` | Integer | `min`, `max` |
| `float` | Decimal | `min`, `max` |
| `name` | Person name | - |
| `email` | Email | - |
| `city` | City | - |
| `country` | Country | - |
| `phone` | Phone number | - |
| `address` | Full address | - |
| `company` | Company | - |
| `job` | Job title | - |
| `ip_address` | IPv4 address | - |
| `latitude` | Latitude | - |
| `longitude` | Longitude | - |
| `credit_card` | Fake credit card | - |
| `iban` | Fake IBAN | - |
| `url` | URL | - |
| `choice` | Categorical options | `options` |
| `datetime` | ISO 8601 timestamp | - |
| `uuid` | UUID4 | - |
| `timeseries` | Synthetic time series | `base_value`, `trend_slope`, `seasonal_amplitude`, `seasonal_period`, `noise_level` |

## Troubleshooting

- `GROQ_API_KEY not configured`: check `.env` and restart compose.
- `Error calling GROQ API`: verify key validity, internet access, and quota.
- Generated schema is not exact: use a more specific prompt and then edit fields manually.

## Notes

- Model: `llama-3.3-70b-versatile`
- Temperature: `0.7`
- Max tokens: `2048`
- Typical response time: `2-5s`

Need help? Open an issue at [GitHub](https://github.com/JesusRosaB/SynthDataFactory/issues).
