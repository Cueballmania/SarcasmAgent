# Sarcasm detector

A UV/FastAPI audience app using **GPT-5.4 mini**, PostgreSQL/SQLAlchemy and
Langfuse `observe` plus instrumented Responses parsing. Success returns exactly
`Sarcasm Detected`, `No Sarcasm Detected`, or `Unknown`; failures are explicit
non-success responses, never disguised as Unknown.

## Local setup

Use Python 3.12.12 and UV 0.13.7. `.env` and editor swap files are ignored.
Copy `.env.example` to `.env`, fill credentials, a PostgreSQL URL and a
random signing key; never commit populated credentials:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
uv sync --locked --group eval
uv run --locked --no-dev alembic upgrade head
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Use an explicitly isolated local database. Render's internal database URL works
inside Render, not on your laptop; external connections require the database's
external URL and appropriate TLS/access permissions. Migrations/maintenance use
database-only settings, never construct provider clients, and must not target
shared/production resources without operator approval.

The API accepts `POST /api/classify` JSON `{"message":"your text"}`.
The page is `/`; `/health` checks configuration/schema, not the paid model.

## Your already-connected Render service

Do not create a duplicate Blueprint service. In the **existing service's Settings**
use:

| Setting | Value |
|---|---|
| Build command | `uv sync --locked --no-dev` |
| Start command | `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log` |
| Health check path | `/health` |
| Automatic deploys | Off until reviewed quality/release gates are satisfied |
| Topology | One instance, one Uvicorn worker |

Set `PYTHON_VERSION=3.12.12`, `UV_VERSION=0.13.7`, `APP_ENV=production`.
The server also detects Render and refuses local/test mode there.
`RENDER_GIT_COMMIT` provides deployment revision automatically; optionally supply
a real `DEPLOY_REVISION`, not a `local` placeholder.

Your API keys alone are **not the complete production configuration**. Under
**web service → Environment**, supply:

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` | OpenAI API project key with billing/model access |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Langfuse project credentials |
| `LANGFUSE_BASE_URL` | Approved HTTPS project endpoint/region |
| `DATABASE_URL` | Same-region Render Postgres **Internal Database URL**, preserving TLS options |
| `SESSION_SIGNING_KEY` | At least 32 random characters; never reuse an API key |
| `PUBLIC_BASE_URL` | Actual canonical HTTPS root URL, without credentials/query/fragment |
| `GLOBAL_WINDOW_LIMIT`, `GLOBAL_DAY_LIMIT` | Approved model attempts per UTC minute/day |
| `SESSION_WINDOW_LIMIT` | Per signed session per UTC minute; not authentication |
| `HTTP_WINDOW_LIMIT`, `HTTP_MAX_INFLIGHT` | All-HTTP requests per process minute and active request cap |
| `AUDIT_TIMEOUT_SECONDS` | Positive database acquisition/write limit, at most 5 seconds |
| `RETENTION_DAYS` | Approved metadata retention, 1–365 days |
| `SESSION_TTL_SECONDS` | Signed fairness cookie lifetime, 60–86400 seconds |

Production fails fast on missing credentials or explicit limits. Local values in
`.env.example` are examples, not approved event capacity. Set global minute limit
no higher than daily limit, and session limit no higher than global minute limit.
Use non-sleeping hosting and a durable backed-up database for an audience event;
the reference `render.yaml` describes a paid-compatible service but authorizes no
purchases and does not create a database.

**Before the first web rollout**, run the locked Alembic upgrade against the
approved database from an authorized Render shell or external operator connection.
Never migrate from each worker's startup. See [operations](docs/operations.md).
Committing/pushing to main can trigger a connected service if automatic deploys
are still enabled; turn them off before pushing unverified release candidates.

## Audience QR

After `PUBLIC_BASE_URL` is set, `/presenter` shows the destination and navigation QR.
Download `/qr.svg` or `/qr.png` from your actual deployed hostname. Both are
standard black-on-white QR codes with a four-module quiet zone. No outside QR
service or key is needed. Read each rendered format with a native phone camera
and verify the destination on the audience network; an encoder test is not that
physical/reachability evidence.

## Verification

Ordinary tests are offline and have no live API keys. For the opt-in local
PostgreSQL wheel and functional headless browser:

```bash
uv sync --locked --group eval --group browser --group local-postgres
uv run --locked --group browser playwright install chromium
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked --group eval --group browser --group local-postgres pytest --local-postgres -q
```

Alternatively supply `TEST_DATABASE_URL` for an explicitly isolated database and
omit `--local-postgres`. Tests create/drop only a uniquely run-owned schema. CI
provisions real PostgreSQL and Chromium; missing required tests/prerequisites fail.
The local PostgreSQL wheel is test-only, not a production server or installed
system service. Chromium checks keyboard/loading/result/error behavior at phone
and desktop widths; they are not a physical-device or screen-reader attestation.

## Evaluations and release

There is deliberately **no invented gold dataset or accuracy claim**. Supply
reviewed JSON data and approved run configuration per [evaluation guide](evals/rubric.md).
Pilot and holdout are separate; group related examples in one split. After setting
authorized credentials and per-run caps:

```bash
uv run --locked --group eval python -m evals.run run \
  --live --split pilot --dataset /approved/dataset.json \
  --config /approved/run.json --report reports/pilot.json
uv run --locked --group eval python -m evals.run run \
  --live --split holdout --dataset /approved/dataset.json \
  --config /approved/run.json --report reports/holdout.json
uv run --locked --group eval python -m evals.run check \
  --dataset /approved/dataset.json --config /approved/run.json \
  --report reports/holdout.json --revision YOUR_CANDIDATE_COMMIT_SHA
```

Pilot-only/nonpassing reports exit nonzero, even when the report was successfully
written. Quality metrics include exact match, confusion matrix, macro-F1,
per-class precision/recall/support, abstention/coverage/answered accuracy, failure
rate, latency and available cost. Unknown billing data remains unknown.
Live runs require explicit `--live`, reviewed non-fixture data, authorization,
request/concurrency/token/cost caps and thresholds; PR CI never makes paid calls.

Rollout consumes both the exact revision's successful CI `checks` job and the
current passing holdout checker. Render's skipped/neutral check acceptance is not
sufficient quality evidence. After rollout, verify HTTPS, audit/trace linkage,
privacy masking, approved isolated load/recovery and the actual QR phone scan.
