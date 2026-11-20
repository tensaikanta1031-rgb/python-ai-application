# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Personal AI writing tool (blog posts, email replies, summaries, rewriting, translation, SNS posts, titles, free-form) built with Python + Streamlit + Gemini API (`google-genai` SDK). Single user, no database, no auth. UI text and prompts are in Japanese.

## Commands

Windows / PowerShell. Dependencies are installed in `.venv`; call its Python directly rather than relying on activation or the global `pip`.

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
.venv\Scripts\python -m streamlit run app.py --server.headless true   # when launched non-interactively
```

After changing a helper module's public names (e.g. adding a function to `gemini_client.py` that `app.py` imports), restart the running Streamlit server. A running server can keep the old module and raise `ImportError` even though the file is correct.

When starting the app from a non-interactive shell, pass `--server.headless true`. Otherwise Streamlit's first-run email prompt blocks on stdin and the process exits (code 255).

No test suite or linter is configured. To smoke-test the UI headlessly, use `streamlit.testing.v1.AppTest`. Pass `AppTest.from_file` an absolute path, because relative paths resolve against the calling script's directory, not the working directory. Then select each tool through the sidebar radio (`at.sidebar.radio[0].set_value(tool)`) and check `at.exception`.

The API key comes from `GEMINI_API_KEY` in `.env` (loaded via python-dotenv). If it is missing, the sidebar asks for the key instead.

## Architecture

The code has three layers, each in its own file:

- **`tools.py`** is the registry of writing tools. Each tool is a `Tool(key, label, icon, description, render)` in the `TOOLS` list. `render()` draws that tool's Streamlit input widgets and returns a `Prompt(system, user, required)`:
  - `required` maps a display label to an input value; `app.py` blocks generation while any of them is empty.
  - All tools share `BASE_SYSTEM`, which tells the model to output only the deliverable, in Markdown, with no preamble.
  - `_line(label, value)` adds an optional condition to the prompt only when the field is filled.
  - `_text_or_file(label, key)` is a paste-or-upload input (txt/md/pdf/docx via `file_loader.py`). Its widget keys are derived from `key`, so each call needs a unique `key`.
- **`app.py`** is the generic shell and contains no tool-specific code. It holds:
  - the sidebar: tool picker, API key, model selector, and temperature. The model options come from the API via `gemini_client.list_text_models()`, cached for an hour; `DEFAULT_MODEL` always comes first and is the only option if the list can't be fetched. There is also a free-text "その他" entry. Gemini model names get retired: `gemini-2.5-flash` returns 404 "no longer available to new users", so don't hard-code older models.
  - the generate button and its validation;
  - streaming output via `st.write_stream`;
  - the result view, with copy and Markdown download.
- **`gemini_client.py`** has `stream_generate()`. It takes a conversation (`list[Message]`, where `Message` is a `(role, text)` tuple and role is `"user"` or `"model"`), creates a `genai.Client` on every call, and yields text chunks from `generate_content_stream`. Temporary errors (500/503/504) are retried with the waits in `RETRY_WAITS`, but only if no text has been yielded yet; retrying after partial output would duplicate text. `friendly_error()` turns API errors into Japanese guidance for the UI.

To add a tool, write a `render_xxx()` function that returns a `Prompt` and append a `Tool(...)` to `TOOLS`. The sidebar picks it up automatically, so `app.py` needs no changes.

### State flow

- `st.session_state.results[tool.key]` is `{"system", "messages"}`. `messages` is the whole conversation; the last `("model", text)` entry is the result on screen.
- Refining (the quick buttons in `QUICK_REFINES` or the free-text form) sends `messages + [("user", instruction)]` back to Gemini. Each refine appends an instruction/result pair. "↩️ 1つ戻す" drops the last pair.
- `st.session_state.history` is loaded from `history.json` through `history_store.py` (gitignored, newest first, capped at `MAX_ITEMS`). The sidebar shows 20 entries.
- `app.py:generate()` handles both new generations and refines. It streams the output, stores the result, saves history, then calls `st.rerun()`. After the rerun, the result view renders the text from `results`; the streamed copy is shown only during that one run.
