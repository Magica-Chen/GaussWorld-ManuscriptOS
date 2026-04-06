# Auth

## OpenAI

OpenAI is the default synthesis provider and should use a PKCE-style OAuth flow modeled after the OpenClaw pattern:

- generate verifier/challenge and random state
- open browser to provider authorization URL
- try local callback capture
- fall back to manual paste if headless
- store access and refresh metadata in a local profile store
- attempt bearer-token provider execution from the stored profile
- fall back to `OPENAI_API_KEY` or `GW_MOS_OPENAI_ACCESS_TOKEN` from the environment when no local profile is present

## Anthropic

Anthropic is the adversarial reviewer in v1 and should use API-key auth only.

- local profile store via `gw-mos auth add anthropic --api-key ...`
- environment fallback via `ANTHROPIC_API_KEY`
