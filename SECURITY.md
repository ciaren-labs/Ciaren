# Security Policy

## Security Status

### AI-Assisted Development

Parts of this project have been written or reviewed with AI assistance. All
contributions still need human review, tests, and security-minded maintenance.
Ciaren is alpha software and has not yet completed a formal independent
third-party security audit.

What this means in practice:

- Security-sensitive changes are reviewed and tested, but undiscovered issues may
  still exist.
- The recommended deployment model is local-first or behind your own trusted
  access controls.
- For production or regulated environments, run your own review, threat model,
  and operational controls before relying on Ciaren.
- Privacy protections follow the local-first trust model described below.

**Users and contributors should:**

1. **Review changes carefully** when using Ciaren in sensitive environments.
2. **Test thoroughly** with representative data and edge cases before deploying.
3. **Use trusted access controls** if binding outside localhost.
4. **Report security issues responsibly** using the process below.
5. **Track limitations explicitly** when adopting alpha features.

---

## Known Limitations

### Alpha Phase

Ciaren is in active development. Known limitations include:

- **No encryption at rest** — data is stored in plaintext (use SQLite for local-only setups)
- **No authentication by default** — assumes a trusted local environment; set
  `CIAREN_API_TOKEN` when binding outside loopback or placing Ciaren behind
  an authenticating reverse proxy. State-changing API requests from a browser
  are protected by an origin guard (CSRF/DNS-rebinding defense): the `Origin`
  must be a `CIAREN_CORS_ORIGINS` entry or a local/`CIAREN_TRUSTED_HOSTS`
  hostname
- **Evolving input validation** — edge cases continue to be hardened as the
  project matures
- **Limited audit logging** — detailed administrative audit logs are not yet a
  core feature
- **Plugins run unsandboxed** — an enabled plugin is ordinary Python that runs
  with your account's access; declared permissions are a consent/disclosure
  boundary, not a sandbox. Only install plugins whose source you trust and can
  inspect (a `.ciarenplugin` is a zip you can unzip and read). An opt-in audit-hook
  layer (`CIAREN_PLUGIN_PERMISSION_ENFORCEMENT=warn|enforce`) can log or block
  ungranted network/file-write/subprocess/shell actions, but is not containment.
  See [Plugin Security](docs/security/plugin-security.md)
- **Flow parameters are text substitution, not bound values** — `{{ name }}` is
  a plain string replacement performed before a node's config is used. Most
  fields are inert once substituted, but a parameter referenced inside a
  `pythonTransform` script, a `filterExpression`/`assertExpression`/derived-column
  expression, or a `sqlInput` query (in "query" mode) is substituted into code/query text that
  is then executed/evaluated — an override supplied at run time can inject
  statements or change query logic, not just a value. This is consistent with
  "pythonTransform runs unsandboxed" and "SQL `read_query` is arbitrary SQL by
  design" above: only let a caller supply run-time parameter overrides for a
  flow if they're as trusted as the flow's author. See the security note in
  [docs/guide/parameters.md](docs/guide/parameters.md#tips-gotchas)
- **Pandas dataframe limits** — no compression, large datasets may be slow or fail

### Needs Additional Controls For

- **Personal identifiable information (PII)** — add your own data protection,
  retention, and access controls
- **HIPAA/GDPR regulated data** — Ciaren does not currently provide a
  compliance program or certification
- **High-volume production ETL** — not designed for 100GB+ datasets
- **Real-time pipelines** — batch-only, no streaming support
- **Shared multi-user environments** — add authentication, authorization, and
  network controls around the app

---

## Best Practices

### For Users

1. **Run locally** — don't expose to the internet without auth layer
2. **Use test data first** — verify flows work before touching production data
3. **Review exported code** — the Python output is your source of truth
4. **Back up your data** — before running any transformation
5. **Start small** — test with 1K rows before processing 1M rows
6. **Version your flows** — use git or manual backups
7. **Install only trusted plugins** — review a plugin's code before approving it;
   it runs unsandboxed with your access

### For Contributors

1. **Validate all inputs** — at system boundaries
2. **Use parameterized queries** — avoid SQL injection
3. **Test edge cases** — null values, empty datasets, large datasets
4. **Follow OWASP top 10** — don't introduce common vulnerabilities
5. **Use type hints** — helps catch many bugs early
6. **Write tests** — especially for security-sensitive code
7. **Review AI-assisted code carefully** — verify it does what you expect

---

## Dependencies

We use:
- **FastAPI** — actively maintained, good security track record
- **SQLAlchemy** — parameterized queries prevent SQL injection
- **Pandas** — well-tested, but be aware of its limitations with untrusted data
- **Pydantic** — validates inputs before processing

**Keep dependencies updated:**
```bash
# Backend
pip list --outdated
pip install --upgrade <package>

# Frontend
npm outdated
npm update
```

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report suspected vulnerabilities privately via
[GitHub Security Advisories](https://github.com/ciaren-labs/Ciaren/security/advisories/new)
("Report a vulnerability"). Include what you found, how to reproduce it, and
the impact you believe it has. Proof-of-concept steps help a lot.

What to expect:

- Acknowledgement as soon as possible — Ciaren is maintained by a single
  person, so please allow up to **7 days** for a first response.
- If confirmed, a fix is prioritized ahead of other work and credited to you
  in the release notes unless you prefer otherwise.
- Please give us reasonable time to ship a fix before public disclosure.

### Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release (0.x) | ✅ Security fixes |
| Older 0.x releases | ❌ Please upgrade to the latest release |

Until 1.0.0, security fixes land in the latest release only — there are no
long-term support branches during the alpha phase.

---

## Reporting Other Issues

For non-security issues:

- **Bugs:** [Open a GitHub Issue](https://github.com/ciaren-labs/Ciaren/issues)
- **Questions:** [GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)
- **Performance concerns:** Include dataset size, transformation complexity, timing info

**Thank you for helping keep Ciaren safe and secure.**
