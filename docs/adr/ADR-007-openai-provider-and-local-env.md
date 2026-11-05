# ADR-007: OpenAI-compatible provider and local environment configuration

## Status

Accepted

## Date

2026-11-04

## Context

WorthRot's facts extraction pipeline needs to use the Bazaarlink hosted
`qwen/qwen3.7-flash:free` model instead of OpenAI's own API. The provider
should remain configurable by model name and base URL, and local development
should support a root `.env` file without committing keys.

## Decision

Use Bazaarlink's OpenAI-compatible Chat Completions endpoint for fact
extraction. Configure it through `BAZAARLINK_API_KEY`, `LLM_BASE_URL`, and
`MODEL_NAME`, defaulting to Bazaarlink's `/v1` API and
`qwen/qwen3.7-flash:free`. Load a root `.env` file for local development using
`python-dotenv`; do not override environment variables already supplied by the
shell or hosting platform. Keep `.env` Git-ignored and provide `.env.example`
as the safe template.

## Options

- Use OpenAI's own hosted API.
- Add an API client SDK.
- Call the compatible HTTP API with the existing Python standard library.

## Trade-offs

The existing HTTP client avoids adding a provider SDK, while `python-dotenv`
keeps local setup straightforward. The provider must implement the compatible
Chat Completions request and response shape.

## Consequences

- Local development reads `BAZAARLINK_API_KEY`, `LLM_BASE_URL`, and
  `MODEL_NAME` from the repository-root `.env`.
- Hosted deployments must configure these values through their environment
  configuration.
- Requests and token-usage parsing use the OpenAI-compatible Chat Completions
  contract.
- Existing transcript verification and verdict mapping remain unchanged.

## Action Items

- Keep the API request and response parsing covered by mocked tests.
- Never commit a populated `.env` file or expose the API key in logs.
