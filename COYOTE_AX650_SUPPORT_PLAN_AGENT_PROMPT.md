# COYOTE AX650 SUPPORT PLAN - CODING AGENT EXECUTION PROMPT

## Role and Mission
You are the coding agent for `ax650_raspberry_pi_services/coyote_interactive`.
Implement support for a third LLM provider option: `ax650`.

Existing providers: `azure`, `ollama`.
New provider must integrate with local AX650 services used by this repository.

## Hard Requirements (Must Implement Exactly)
1. Add `ax650` as a valid `LLM` option.
2. AX650 generation must call Ollama-compatible endpoint on port `11434`.
3. AX650 generation must send only the latest prompt for the current turn.
4. AX650 generation must never send full `messages`/transcript history.
5. AX650 reset/control must call runtime endpoints on port `8000`.
6. Startup behavior when `LLM == "ax650"`:
   - execute AX650 soft reset sequence
   - reassert `SYSTEM_MESSAGE_TEXT`
7. Full reset behavior (BOOM archive event) when `LLM == "ax650"`:
   - keep local archive behavior
   - execute AX650 soft reset sequence
   - reassert `SYSTEM_MESSAGE_TEXT`
8. Keep existing `azure` and `ollama` behavior unchanged.
9. Keep local conversation file logging and archive history intact.

## Confirmed Endpoint Contracts

### Generation
- URL: `http://localhost:11434/api/generate`
- Request:
```json
{
  "model": "qwen3-ax650",
  "prompt": "<latest prompt only>",
  "stream": false
}
```
- Expected response field to parse first: `response`

### Runtime Reset / Control
- Stop: `GET http://127.0.0.1:8000/api/stop`
- Reset: `POST http://127.0.0.1:8000/api/reset`
- Reset body:
```json
{
  "system_prompt": "<config.SYSTEM_MESSAGE_TEXT>"
}
```
- Required order: stop first, then reset.

## Files You Must Update
1. `ax650_raspberry_pi_services/coyote_interactive/config_secrets.example.py`
2. `ax650_raspberry_pi_services/coyote_interactive/config.py`
3. `ax650_raspberry_pi_services/coyote_interactive/llm_chat_completion.py`
4. `ax650_raspberry_pi_services/coyote_interactive/coyote.py`
5. `ax650_raspberry_pi_services/coyote_interactive/README.md`
6. `ax650_raspberry_pi_services/coyote_interactive/INSTALL.md`
7. `ax650_raspberry_pi_services/coyote_interactive/TROUBLESHOOTING.md`

## Implementation Checklist

### Step 1: Config Surface
In `config_secrets.example.py`, add AX650 settings with defaults:
- `AX650_GENERATE_ENDPOINT = "http://localhost:11434/api/generate"`
- `AX650_RUNTIME_STOP_ENDPOINT = "http://127.0.0.1:8000/api/stop"`
- `AX650_RUNTIME_RESET_ENDPOINT = "http://127.0.0.1:8000/api/reset"`
- `AX650_MODEL = "qwen3-ax650"`
- `AX650_TIMEOUT_SECONDS = 30`

In `config.py`:
- update `LLM` comments/documentation to include `ax650`.
- do not force default provider switch unless explicitly requested.

### Step 2: AX650 Provider Adapter
In `llm_chat_completion.py`:
- add `chat_completion_ax650(conversation_file)`.
- add helper to extract latest user prompt from local conversation JSON.
- add dispatcher branch:
  - `elif config.LLM == "ax650": return chat_completion_ax650(conversation_file)`

AX650 generation rules:
- load conversation file locally for context extraction only.
- locate newest message where `role == "user"`.
- submit only that text as `prompt`.
- include timeout and defensive exception handling.
- parse response from `response` field.
- if invalid response, return safe fallback text and log error.

### Step 3: Shared Reset Helper
Add a reusable helper for AX650 reset sequence:
- call stop endpoint
- call reset endpoint with `system_prompt = config.SYSTEM_MESSAGE_TEXT`
- wrap in robust error handling

This helper should be callable from startup and BOOM flow.
Avoid duplicating raw HTTP logic in multiple files.

### Step 4: Startup Reset Hook
In `coyote.py`, during startup path before active interaction handling:
- if `config.LLM == "ax650"`, invoke AX650 reset helper.
- startup should continue even if reset fails (log clear error).

### Step 5: BOOM Reset Hook
In `coyote.py` BOOM path (sleep mode + both buttons):
- preserve archive behavior exactly.
- after archive, if `config.LLM == "ax650"`, invoke AX650 reset helper.
- BOOM flow should still complete even if AX650 reset fails.

### Step 6: Docs
Update README/INSTALL/TROUBLESHOOTING to include:
- `ax650` as provider option.
- required AX650 config keys.
- stateful runtime behavior explanation.
- latest-prompt-only rule.
- startup + BOOM reset behavior.
- troubleshooting curl checks for both services (`11434`, `8000`).

## Guardrails and Non-Regression Rules
1. Do not break Azure integration.
2. Do not break Ollama integration.
3. Do not remove current conversation append/archive behavior.
4. Do not move provider logic into unrelated modules unless minimal and justified.
5. Keep edits focused and minimal.

## Test Requirements

### Unit Tests (Mock HTTP)
Add tests to verify:
1. dispatcher selects AX650 branch.
2. AX650 request contains `prompt` from newest user message only.
3. AX650 request does not include full `messages` array.
4. AX650 parser uses `response` field.
5. network failure returns safe fallback string.
6. malformed JSON/missing response field returns safe fallback string.
7. reset helper sends stop then reset with correct system prompt.

### Manual Validation Checklist
1. Set `LLM = "ax650"`.
2. Start service and confirm startup reset occurs.
3. Trigger TV interaction and verify spoken response.
4. Trigger person interaction and verify conversational continuity.
5. Trigger BOOM in sleep mode and verify:
   - archive file created
   - AX650 reset invoked
   - next interaction behaves as fresh session persona
6. Temporarily break `:8000` or `:11434` and confirm graceful fallback/no crash.

## Definition of Done
All items below must be true:
1. AX650 provider works end-to-end with latest-prompt-only generation.
2. Startup reset and BOOM reset both call stop/reset + system prompt assertion.
3. Existing providers remain functional.
4. Local conversation logs and archive files remain functional.
5. Docs updated in required files.
6. Added/updated tests pass.

## Required Final Delivery From Coding Agent
Provide a final implementation report containing:
1. Summary of all files changed.
2. Exact behavior implemented for AX650 generation and reset.
3. Test results (unit + manual checklist outcomes).
4. Any known limitations or follow-up recommendations.

## Additive Context Validation Protocol (Mandatory)

Run this protocol whenever validating long-conversation behavior in AX650 mode.

### Objective

Separate and measure:
1. Additive runtime-memory behavior (latest-prompt-only, no full transcript resend).
2. Effective runtime context ceiling in the currently deployed binary/model path.

### Preconditions

1. Endpoints reachable:
  - `http://127.0.0.1:11434/api/generate`
  - `http://127.0.0.1:8000/api/stop`
  - `http://127.0.0.1:8000/api/reset`
2. `LLM = "ax650"`.
3. Runtime responds quickly to `GET /api/stop` before tests.

### Arm A: Additive Memory Stress

1. Call stop then reset with `system_prompt` once.
2. Send repeated `/api/generate` requests with only latest prompt text.
3. Use deterministic long prompts and fixed `num_predict` to make runs comparable.
4. Record per turn:
  - status code
  - latency
  - text snippet
  - context-full marker (`SetKVCache failed` / `context may be full`)

Expected:
- early turns succeed, then fail once KV cache budget is exhausted.

### Arm B: Reset-Each-Turn Control

1. For each turn, call stop+reset before generate.
2. Send the same prompt structure used in Arm A.
3. Record the same metrics.

Expected:
- sustained success over many turns if failures in Arm A were accumulation-driven.

### Runtime Capability Check

Run runtime help and capture options:

```bash
./main_api_axcl_aarch64 --help
```

If no context-length option exists, do not assume runtime can apply large context values just because proxy-layer config reports a larger number.

### Current Measured Findings (2026-07-26)

1. Runtime help has no explicit context-length CLI option.
2. After clean restart, backend health reported `context_window_tokens: 1024`.
3. Additive arm failed at turn 3 with context-full message.
4. Reset-each-turn control succeeded 10/10 with identical prompt structure.

Conclusion:
- latest-prompt-only transport is implemented correctly;
- additive memory is active;
- practical context budget remains too small for long transcript-heavy conversations in current runtime/model deployment.

### Design Guidance for Long Sessions

To meet the project goal (hot-loaded additive conversation + deep usable context):
1. Keep latest-prompt-only outbound behavior.
2. Increase true runtime/model context capacity (not only proxy config).
3. Add budget-aware summarize-then-reset lifecycle when native context remains constrained.
