# khsd-nexus-chat

Backend service for the Nexus ChatKit frontend. This FastAPI app exposes the single `/chatkit` endpoint required by the [ChatKit Python server](https://openai.github.io/chatkit-python/server/) and uses an in-memory store for threads and attachments (swap in a database-backed store later).

## Backend setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # or source .venv/bin/activate on macOS/Linux
   pip install -r requirements.txt
   ```

2. Provide your OpenAI credentials (the OpenAI SDK reads standard env vars). You can also drop them into a `.env` file:

   ```bash
   setx OPENAI_API_KEY "<your key>"  # or export on macOS/Linux
   ```

   Useful overrides:

   - `DATABASE_URL` – switch to PostgreSQL storage (e.g. `postgresql+psycopg://chatkit:chatkit@localhost:5432/chatkit`).
   - `CHATKIT_PUBLIC_BASE_URL` – base URL exposed to the frontend (defaults to `http://localhost:8000`).
   - `CHATKIT_DOMAIN_KEY` – domain key from the OpenAI dashboard.
   - `CHATKIT_GREETING` / `CHATKIT_PLACEHOLDER` – customize the start screen and composer text.
   - `CHATKIT_START_SCREEN_PROMPTS_JSON` – JSON array of `{ "label": "...", "prompt": "..." }` shown on the start screen.
   - `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST` – enable Langfuse tracing via `app/instrumentation.py`.
   - `FIN_STR` – ODBC connection string for the PeopleSoft data warehouse used by the `get_department_supplier_actuals` tool.

3. Start the server:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   ChatKit will POST to `http://localhost:8000/chatkit`. Health probe is at `/health`.

## Frontend (ChatKit React example)

The `frontend` directory contains a Vite + React app with the ChatKit web component wired to this backend.

1. Install dependencies once:

   ```bash
   cd frontend
   npm install
   ```

2. Copy `frontend/.env.example` (create one) and set at least:

   ```bash
   VITE_CHATKIT_USER_ID=demo-user                 # forwarded to the backend as X-User-Id
   # Optional for debugging protected APIs:
   # VITE_CHATKIT_CONFIG_URL=http://localhost:8000/chatkit/config
   # VITE_CHATKIT_AUTH_TOKEN=...
   ```

3. Start the dev server with `npm run dev` (default port 5173). The ChatKit UI fetches `/chatkit/config` to discover the backend URL, domain key, greeting, placeholder, and start-screen prompts.

   **Important:** `ChatKitSurface` injects `https://cdn.platform.openai.com/deployments/chatkit/chatkit.js` on mount so the `<openai-chatkit>` element exists before React renders it. If you reorganize the frontend, keep that script loader and the `uploadStrategy` config the ChatKit docs require for custom backends.

## Endpoints

- `POST /chatkit`: Entry point for ChatKit requests. Streams SSE or returns JSON according to the ChatKit server contract.
- `GET /chatkit/config`: Returns the public configuration consumed by the frontend.
- `POST /attachments/{attachment_id}/upload`: Upload bytes for a previously registered attachment (uses in-memory storage and clears the `upload_url` flag).
- `GET /attachments/{attachment_id}`: Retrieve stored bytes for debugging or previews.

## Notes

- Without `DATABASE_URL`, storage falls back to in-memory (`InMemoryStore` and `InMemoryAttachmentStore`). Restarting the process clears all threads, items, and uploads. Set `DATABASE_URL` to keep everything in PostgreSQL.
- The server uses the OpenAI Agents SDK via `openai-chatkit`. Update the default model or instructions in `app/config.py` if you want a different persona.
- The ChatKit agent exposes a `get_department_supplier_actuals` tool that queries PeopleSoft using the SQL in `app/sql/dept_supplier_actuals.sql`. Set `FIN_STR` to a valid SQL Server ODBC connection string so the tool can run.

## Langfuse tracing

OpenAI Agents emits spans through the OpenInference instrumentation so Langfuse can capture end-to-end traces.

1. Install + configure Langfuse credentials (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, and optionally `LANGFUSE_HOST`).
2. The backend imports `app/instrumentation.py` on startup. It calls `OpenAIAgentsInstrumentor().instrument()` (from `openinference-instrumentation-openai-agents`) and boots the Langfuse client via `langfuse.get_client()`.
3. When the required environment variables are missing, the instrumentation quietly skips itself.

After the service boots you can inspect traces in Langfuse (LLM spans, tool calls, etc.) with no changes to the agent logic.
- Set `DATABASE_URL` to enable the PostgreSQL store. Run `alembic upgrade head` after changing models.

## Database & migrations

When `DATABASE_URL` is set, ChatKit threads, items, and attachments are persisted via SQLAlchemy.

```bash
export DATABASE_URL=postgresql+psycopg://chatkit:chatkit@localhost:5432/chatkit
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Alembic reads your `.env`, so the same connection string is used for migrations and runtime.

## Docker Compose

Spin up Postgres, the FastAPI backend, and the Vite dev server together:

```bash
docker compose up --build
```

The stack exposes:

- Postgres on `localhost:5432`
- Backend on `http://localhost:8000`
- Frontend on `http://localhost:5173`

The compose file runs migrations automatically (`alembic upgrade head`) before starting the backend container.
