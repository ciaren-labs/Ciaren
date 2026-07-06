## Summary

<!-- Describe the change in 1-3 sentences. Focus on user-visible behavior or maintainer impact. -->

## Related Work

<!-- Link issues, discussions, design notes, or prior PRs. Use "Closes #123" when this should close an issue. -->

- Closes #
- Related to #

## Preflight

- [ ] I searched existing issues and PRs to avoid duplicate work.
- [ ] This PR targets `main`.
- [ ] This PR is focused on one bug, feature, documentation update, or maintenance task.
- [ ] Large or breaking changes were discussed in an issue or discussion before implementation.
- [ ] New niche connectors/integrations are implemented as plugins or were explicitly accepted by maintainers for core.
- [ ] I have read and followed [CONTRIBUTING.md](../CONTRIBUTING.md).
- [ ] All commits are signed off (DCO): `git commit -s`.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Transformation node
- [ ] Connector, storage, or plugin SDK change
- [ ] UI/UX improvement
- [ ] Performance improvement
- [ ] Refactor or internal cleanup
- [ ] Documentation
- [ ] Tests only
- [ ] Dependency, build, or CI maintenance

## Area

- [ ] Frontend/UI
- [ ] Backend/API
- [ ] Flow editor
- [ ] Transformation engine
- [ ] Data connectors/storage
- [ ] Plugins/SDK
- [ ] CLI/client
- [ ] Documentation site
- [ ] Docker/deployment
- [ ] CI/release tooling

## What Changed

<!-- Use concise bullets. Mention important files, APIs, behavior, migrations, or docs. -->

-
-
-

## Behavior and Compatibility

- [ ] No breaking changes
- [ ] Breaking change, documented below
- [ ] User-facing behavior changed
- [ ] Database, flow format, API, or plugin contract changed
- [ ] Requires documentation updates

**Compatibility notes:**

<!-- Explain migration steps, deprecations, changed defaults, or why this is safe. -->

## Testing

<!-- Mark what was actually run. Include commands and relevant manual steps. -->

- [ ] Backend tests: `pytest`
- [ ] Frontend tests: `npm run test`
- [ ] Frontend lint/build: `npm run lint` / `npm run build`
- [ ] Docs build: `npm run docs:build` or VitePress equivalent
- [ ] Connector integration tests
- [ ] Manual testing
- [ ] Not run; explained below

**Commands run:**

```text

```

**Manual test steps and data:**

1.
2.
3.

## Screenshots or Recordings

<!-- Required for UI changes. Include before/after when possible. -->

## Performance, Security, and Data Notes

- [ ] No meaningful performance impact
- [ ] Performance impact measured or explained below
- [ ] No new user input, file, network, or credential handling
- [ ] Security-sensitive behavior reviewed
- [ ] Secrets, tokens, and private data are not included

**Notes:**

<!-- Include timings, dataset sizes, security assumptions, or privacy considerations. -->

## Reviewer Guide

<!-- Tell reviewers where to start and what deserves extra attention. -->

- Start with:
- Pay close attention to:
- Known follow-ups:

## Final Checklist

- [ ] Type hints are present for new Python functions.
- [ ] TypeScript changes avoid unexplained `any`.
- [ ] Tests cover the main success and failure paths.
- [ ] Documentation, examples, or changelog notes were updated when needed.
- [ ] Error messages are actionable for users.
- [ ] AI-assisted code was reviewed carefully for correctness and edge cases.
