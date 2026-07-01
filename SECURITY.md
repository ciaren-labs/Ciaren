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
  an authenticating reverse proxy
- **Evolving input validation** — edge cases continue to be hardened as the
  project matures
- **Limited audit logging** — detailed administrative audit logs are not yet a
  core feature
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

## Reporting Other Issues

For non-security issues:

- **Bugs:** [Open a GitHub Issue](https://github.com/ciaren-labs/Ciaren/issues)
- **Questions:** [GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)
- **Performance concerns:** Include dataset size, transformation complexity, timing info

**Thank you for helping keep Ciaren safe and secure.**
