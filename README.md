# khsd-nexus-chat

Backend service for the Nexus ChatKit frontend. This FastAPI app exposes the single `/chatkit` endpoint required by the [ChatKit Python server](https://openai.github.io/chatkit-python/server/) and uses an in-memory store for threads and attachments (swap in a database-backed store later).

## Getting started

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

3. Start the server:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   ChatKit will POST to `http://localhost:8000/chatkit`. Health probe is at `/health`.

## Endpoints

- `POST /chatkit`: Entry point for ChatKit requests. Streams SSE or returns JSON according to the ChatKit server contract.
- `POST /attachments/{attachment_id}/upload`: Upload bytes for a previously registered attachment (uses in-memory storage and clears the `upload_url` flag).
- `GET /attachments/{attachment_id}`: Retrieve stored bytes for debugging or previews.

## Notes

- Storage is purely in-memory right now (`InMemoryStore` and `InMemoryAttachmentStore`). Restarting the process clears all threads, items, and uploads. These classes are isolated in `app/stores.py` so a database-backed version can be dropped in later.
- The server uses the OpenAI Agents SDK via `openai-chatkit`. Update the default model or instructions in `app/config.py` if you want a different persona.
