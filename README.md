# Aymora Weekly Drop

A working prototype of the engine behind "one introduction, every week, never a weak one".
Built for Aymora's Tech Challenge. Read [WRITEUP.md](WRITEUP.md) for the what, why and how.

## Run it

```
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Open http://localhost:8000. Or use the Dockerfile, or deploy with `render.yaml`.

```
python -m pytest -q          # 73 tests
python -m scripts.run_sim    # prints the numbers quoted in the write-up
```

## What is in the demo

- **Your drop**: answer ten short scenarios, get a weekly introduction with reasons, double opt-in, feedback that retunes your weights, and a button to jump to next week.
- **Engine room**: leads with "Can Aymora keep its promise?" (delivered vs ceiling, who it works for, what it takes, scam red team, ghosting and closure, three ways to run the week), all re-run by sliders.
- **Boundaries, safe reveal, closure, report**: in the drop view. A demo control simulates a scam attempt.
- **How it works**: the pipeline in plain words, and what is real versus not.

## Layout

```
app/        engine (compat, drop, sim, learn, explain), API (main), sandbox (world)
static/     front end, plain JavaScript, no build step
tests/      73 tests
scripts/    run_sim.py
docs/       notes on Aymora's public positioning
```

Optional: set `AYMORA_LLM=1` and `GROQ_API_KEY` to let a language model read free text and soften explanations. The engine never depends on it, and falls back to deterministic output.
