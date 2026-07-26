# Adjustable Context Window Plan

## Goal

Add configurable context-window support for the parent-project AX650 inference service so the effective conversation length is no longer hard-coded to 1024 tokens.

## Scope

This change is limited to the parent project under [ollama_ax650_integration_mvp](ollama_ax650_integration_mvp) and does not modify the git submodules under [ollama](ollama).

## Design Goals

- Keep the current default behavior compatible with the existing deployment.
- Allow the context window to be configured at service startup.
- Allow the context window to be changed at runtime through the service API.
- Reinitialize state safely whenever the window changes so prior conversation/KV-cache state does not leak across requests.

## Proposed Behavior

### Startup configuration

The service will read a new environment variable:

- AX650_MAX_CONTEXT_TOKENS

Default value: 1024

### Runtime API

The service will expose:

- GET /config/context-window
- POST /config/context-window

Example payload:

```json
{
  "context_window_tokens": 2048
}
```

Changing the value will reset the active runtime state before the next generation request so the new window takes effect cleanly.

## Implementation Notes

### Inference engine

The parent-side inference engine will:

- store the active context window on the backend instance
- use it when allocating KV caches
- use it when terminating the generation loop
- provide a setter method for runtime updates

### Service backend

The parent-side Flask backend will:

- read the startup setting from the environment
- expose the context-window config through the API
- update the active backend instance when the API is called
- trigger a reset/reinitialize flow so the new setting is applied safely

## Validation

The implementation will be verified with:

- a unit-style smoke test for backend context-window updates
- a Flask endpoint test covering GET/POST for the config endpoint
