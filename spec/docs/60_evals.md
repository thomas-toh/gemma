## Chapter 6 - Evaluation of LLMs

**Last reconciled: 2026-08-04 02:35** · Build progress: [STATE.md](../plans/STATE.md) · Harnesses: [eval/](../../eval)

Gemma's model behaviour must be measured for it to be useful. The optimisation here is a balance of cost, latency and accuracy (as with all LLM wrappers), but at least with latency the target is defined as an upper-bound. Since the user is free to select their model, the evaluation (and products that are build on the basis of an evaluation's findings) must be model-agnostic and, particularly, configuration agnostic. Hence the harnesses in `eval/` are intended to produce repeatable outcomes to weed out issues arising from prompting, inference, or backend routing code.

The `eval/` harnesses are maintainer commands, run on the box, and their output is designed to be human- and LLM-readable.

The goal of the `eval/` harnesses is to produce *publishable measurements*, i.e., to ascertain, with respect to a certain given set of configurations and/or parameters, a certain outcome is produced. To this end, the currently-designed `eval/` harnesses investigate (last updated: 2026-08-04 02:30):

| Harness | Target |
|---------|---------|
| `eval/latency.py` | how long does a turn take, and how badly does that vary? |
| `eval/tool_check.py` | does the model pick the right tool, with sensible arguments? |
| `eval/format_check.py` | does dictation cleanup obey its contract without losing words? |
| `eval/replay.py` | does the whole pipeline still work end to end on real recorded speech? |
| `eval/b1_smoke.py` | does a provider authenticate, stream, and complete a tool round at all? |

### Local model response speed

Putting a local model into daily use is a deploy decision, and it rests on two questions: is it fast
enough to sit inside a voice loop, and does it pick the right tool. This evaluation answers the
first — how long a model takes to respond, across a set of representative prompts. Tool selection is
`eval/tool_check.py`, and both want answering before a model is trusted with real turns.

**Local models only.** A local sweep spends the machine's own GPU time and nothing else, so it can
run to hundreds of samples per prompt without a budget conversation. Cloud providers are out of
scope.

Variance matters more than raw speed. The local ask path is **erratic**, which costs a voice product
more than plain slowness: a predictable delay can be designed around, an unpredictable one cannot.
The bar is 15 ms to 1 s of fluctuation; 1 s to 9 s with intermittent total failure sits below it.
Identical input to `qwen3.5:9b` has ranged 1.5 s to 4.6 s over twelve runs, and two sweeps of an
*identical* configuration produced spreads of 14.07 s and 3.21 s. One run in thirty reached 14.58 s
with reasoning already off, which rules out deliberation.

Thirty runs cannot characterise a one-in-thirty event, and a median hides it completely. The suite is
therefore built for volume and reports the tail.

#### What is measured

Two stages. A user waits on both, and no measurement so far has told them apart.

**Speech to text.** The same recorded WAV through the real transcription path, repeatedly. This has
never been measured as a distribution — its numbers exist as single observations scattered through
the log (44 ms, 61 ms, 182 ms, 687 ms cold). A slow tail here feels identical to a slow tail in the
model, and today the two are indistinguishable.

**One model round.** The utterance, the system prompt and the full tool list to the model, timed
until the round completes. The measurement stops at one round: a tool turn runs two, and timing the
executor as well would fold disk and COM latency into a figure about the model.

Every run also records **what the model did** — called a tool, answered in prose without one,
returned nothing, or errored. A run can time two hundred rounds cleanly while the model invents every
answer, and the timings alone would read as a pass. For a question only a tool can answer, a prose
answer **is** the failure, and it occupies the same row in a latency table as a success.

#### How a run is structured

`python -m eval.latency [RUNS]` measures whichever model the router currently resolves for the
`assistant` role. One model per invocation. The picker is the only place a model is chosen, and a
harness that reached around it would measure a configuration the daemon never runs.

A sweep across models is a sequence of those invocations, driven in one command — `planned`. Each
model's block is measured **in isolation and fully resident**, never by cycling models within a run.
A combined run cycling five models over 16 GB of VRAM scored `qwen3.5:9b` at 7 correct in 9, where
three isolated runs scored it 8 in 9 every time. Partial CPU offload under memory pressure changes
the numerics, so a cycling run measures memory pressure and reports it as model quality.

**The offload guard** (`planned`). Before a model's block begins, every other model is evicted and
the runner is asked what it holds. Ollama keeps a model resident for `keep_alive`, and the `/v1` wire
the adapter speaks **ignores** `keep_alive`, so the eviction cannot be asked for on the wire Gemma
normally uses. The harness drops to Ollama's native API for two calls that concern the runner itself:
an eviction, and a query of what is currently resident.

That query reports more than presence. For each resident model it gives both the total size and how
much of that size sits in VRAM, and **the guard compares the two**. Equal means fully resident; less
means the runner has spilled part of the model to CPU, which is the condition that scored one model
two different ways on the same day. Presence alone would have missed it. If anything else is
resident, or the model under test is not wholly in VRAM, the run **aborts rather than measures**. A
partial offload measured as a clean one publishes a wrong number.

The cycle is verified on the box: an eviction empties the resident list, and the reload that follows
took **9.06 s** before producing a single token — the same cold load the boot preload moves off the
first turn.

That native API stays in the harness. The daemon speaks `/v1` and nothing else; the evaluation takes
the exception because its subject is the runner itself. A local runner with no documented eviction —
LM Studio, llama.cpp — gets no guard, and is measured one at a time with the server restarted between
models.

#### The prompt set

One utterance is not enough. Latency tracks what the model *does*, and a prose answer, a tool call
and a refusal are three different amounts of work — pooling them would blend distributions with
different centres and leave a tail that means nothing. Each prompt is therefore measured as its own
distribution and reported separately.

The set lives in `eval/latency/prompts.json` (`planned`). It is harness data, loaded by nothing the
daemon runs, so it stays in `eval/` and never enters `shared/schemas/`.

| Prompt | Shape | Why it is in the set |
|--------|-------|----------------------|
| "what time is it" | a question only a tool can answer | the known-bad case. It has failed both ways — silent with reasoning on, and an invented "16:05 UTC+8 (Hong Kong)" with it off |
| "open Spotify" | a command | the tool-round path that task routing exists to make cheaper; measured at ~3,200 input tokens across two rounds for a five-token request |
| "find the document about the lease" | a retrieval question | a tool call whose arguments the model must compose from the sentence, so it does more work before the round ends |
| "why is the sky blue" | a question needing no tool | the plain prose path, where output length rather than tool selection sets the time |
| "how are you today" | conversational, needing nothing | the false-positive guard: the correct behaviour is to call no tool at all with every tool available |

Prompts cycle **round robin**. Run in consecutive blocks instead, a thermal ramp, a background
process or a runner that slows as it warms would land entirely on whichever prompt ran last and read
as a property of that prompt.

Every run starts a **fresh session**. History does not carry between runs, so run two hundred sends
exactly as many tokens as run one. A sweep that let history accumulate would measure a conversation
growing, which is a real effect and a separate question.

#### Controls

This evaluation is a **field measurement of the shipped configuration**. Temperature and reasoning
are recorded as configured rather than forced to a fixed value, so the result describes each model as
it is actually set up. A reader who takes it for a controlled benchmark will over-read it.

| Variable | How it is controlled |
|----------|---------------------|
| Temperature | **Native — the configured value, recorded.** The subject is how this assistant behaves as configured. Recorded per run, because a stored temperature changes underfoot: the Ollama card acquired a `0.7` between two sweeps on the same night, having resolved to nothing earlier the same evening |
| Output cap | **Held identical across every run and every model.** Output length dominates round time, so a model that is fast because it says less is not fast. Output tokens are recorded per run as well as capped, so verbosity shows in the report instead of hiding inside the timing |
| Reasoning | **Native — the configured effort, recorded.** The single largest known factor: reasoning was present on 30 of 30 rounds and time tracked its length, 110 characters to 1.2 s against 978 characters to 5.5 s. Turning it off cut the median 2.9× and removed the empty round entirely, with tool selection unchanged at 8 in 9 |
| Tool list | **Held identical.** The list is most of the input, and connectors filter it — a connector switched off means fewer tools, fewer tokens and a faster round. The connector state is asserted before the run and recorded in the report |
| System prompt | **Held identical.** It varies with the profile, carrying the user's details and a sentence naming switched-off connectors, so it is recorded verbatim in the report |
| Connection | **One adapter for a model's whole block**, so the TCP and TLS handshake is paid once. Production does the same — the orchestrator caches an adapter across turns — so a per-run client would measure a cost the user never pays |
| Cold load | **Excluded from the distribution and reported separately.** The first round carries the weight load — 9.06 s, measured 2026-08-04 — a real number, and a separate one |
| Machine state | Recorded, since none of it can be held fixed: what else holds VRAM, and what the runner reported resident and how much of it was in VRAM. A background process contending for the GPU is one of the untested candidates for the 14.58 s spike |

Comparing two models therefore compares them as each is configured. Where the configurations differ —
one running reasoning, one not — the report says so, and the difference is part of what is being
measured rather than noise to apologise for.

**Runs per model.** 200 runs per prompt, on the basis that a p99 needs at least 100 samples to rank.
Five prompts at 200 runs is 1,000 rounds, which at a sub-second median takes well under an hour and
costs nothing but GPU time.

Percentiles are nearest-rank, so every figure printed is an observed run rather than an
interpolation between two that never happened. **Below 100 runs the report prints no p99**, since a
p99 drawn from twenty samples is the slowest of twenty runs carrying a percentile's name.

#### Results

Written to `eval/latency/results/` (`planned`), two files per run, both named for the timestamp,
runner and model.

**A Markdown report**, the human artefact. It opens with the conditions — date, machine, GPU, runner,
model, and every control value from the table above, including the ones recorded rather than held. A
number whose conditions went unrecorded cannot be used six months later.

Then one table per prompt:

```
prompt: "what time is it"
n=200   min 0.59   p50 0.68   p95 1.94   p99 3.08   max 14.58   (spread 13.99 s)
        tool call 198/200 · answered without a tool 1/200 · empty 0/200 · errors 1/200
```

Never a mean. A mean hides a rare spike, and the rare spike is what this evaluation is looking for.

Below the tables, three sections, each owed to a specific past mistake:

- **Outliers, listed individually** with their wall-clock time, so a slow run can be matched against
  the corresponding lines in `gemma.log` and `logs/audit.jsonl`. A tail figure says a spike happened;
  only the log says what else was happening.
- **Samples of any non-tool answer**, verbatim. "It answered" and "it answered correctly" look the
  same in a table. The invented Hong Kong clock reading is what this section catches.
- **The cold-load figure**, separately from the distribution.

**A JSONL file** beside it, one line per run — timestamp, elapsed, outcome, output tokens. Raw data,
so a question nobody thought to ask can be answered later without re-running the sweep.

Neither file is a recommendation. The report states what was measured, under what conditions, on what
date, and stops there.

#### What this evaluation cannot settle

It measures one round, so it says nothing about the second round of a tool turn beyond its token
cost, which is already recorded. It says nothing about whether the model chose the *right* tool
beyond the coarse did-it-call-one count — that is the tool-selection evaluation's job, and the two
are read together. And it cannot prove a cause for the spike. It can establish the rate and the
shape, and test whether the candidates already written down — model eviction and reload, GPU
contention, runner queueing — survive a few hundred samples. That much is worth having: every
proposed cure so far has been argued from one or two observations, and two of them were wrong.

### Tool selection

[TBC]

### Dictation cleanup and spoken formatting

[TBC]

### Pipeline replay

[TBC]

### Provider smoke

[TBC]
