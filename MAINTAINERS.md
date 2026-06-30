# Maintainers

This file documents how FlowFrame is maintained and how project decisions are
made as the contributor base grows.

## Current Maintainer

- Rodrigo Arenas — GitHub: [@rodrigo-arenas](https://github.com/rodrigo-arenas)

## Maintainer Responsibilities

- Triage new issues and route questions to Discussions when appropriate.
- Keep `main` stable and use `development` as the integration branch.
- Review pull requests for correctness, tests, security, maintainability, and
  fit with the local-first product scope.
- Keep public documentation aligned with implemented behavior.
- Apply security fixes and coordinate responsible disclosure.

## Review Policy

- Pull requests should target `development`.
- Maintainers may close duplicate, stale, unsupported, or out-of-scope issues.
- Large features, breaking changes, plugin API changes, and security-sensitive
  changes should have an accepted issue or discussion before implementation.
- New contributors are encouraged to start with focused fixes, docs, tests, or
  `good-first-issue` tasks.

## Release Policy

FlowFrame is currently alpha software. Releases should include:

- A short changelog or release notes.
- Passing CI for backend, frontend, docs, packaging, and security checks.
- Clear notes for breaking changes, migration steps, or known limitations.

## Becoming a Maintainer

Maintainer access may be granted to contributors who consistently make high
quality contributions, review others' work constructively, understand the
project's security posture, and help keep the community healthy.
