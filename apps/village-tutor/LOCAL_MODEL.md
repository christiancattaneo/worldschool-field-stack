# Village tutor with a real local model

The tutor works fully offline from `corpus.json`. To answer free-form questions
beyond the corpus while still offline, plug in a local model. The tutor already
speaks the Ollama API, so this is config, not code.

## Real setup (in the field or on a laptop)

1. Install Ollama: https://ollama.com (one binary, runs locally, no cloud).
2. Pull a small multilingual model that fits a field laptop, for example:

```
ollama pull qwen2.5:3b
```

3. Start the tutor pointed at it:

```
OLLAMA_MODEL=qwen2.5:3b python3 app.py --port 8054
```

`OLLAMA_URL` defaults to `http://localhost:11434/api/generate`. Set it only if
Ollama runs elsewhere. If the model is unreachable, the tutor silently falls
back to the offline corpus, so it never hangs without a connection.

## Verify the wiring without downloading a model

A stub mimics the Ollama API so you can prove the passthrough end to end:

```
python3 ollama_stub.py --port 11500
OLLAMA_MODEL=stub OLLAMA_URL=http://127.0.0.1:11500/api/generate \
  python3 -c "import app; print(app.answer('teach me about rivers','en'))"
```

You should see `source: local-model (stub)`. Swap the stub for real Ollama and
nothing else changes.

## Why local, not cloud

The sites have intermittent Starlink. A local model keeps the tutor working when
the link is down, costs nothing per query, and keeps kids' data on the device.
