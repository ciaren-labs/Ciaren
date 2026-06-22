# Security Policy

## ⚠️ Important Disclaimers

### AI-Generated Code Warning

**This project contains code generated or heavily assisted by AI tools (Claude).** While every effort is made to ensure correctness and quality through testing and review, **we cannot guarantee**:

- **Security** — Code may contain vulnerabilities, logic errors, or unsafe patterns
- **Performance** — Generated code may be inefficient or have hidden costs
- **Reliability** — Bugs may exist despite testing
- **Privacy** — No audit of data handling practices beyond code review

**Users and contributors should:**

1. **Review all code before use** — especially in production
2. **Test thoroughly** — with real data and edge cases before deploying
3. **Not use for mission-critical data** — unless you've independently verified it
4. **Report security issues responsibly** — see below
5. **Understand the limitations** — this is an open-source MVP, not enterprise software

---

## Known Limitations

### MVP Phase

FlowFrame is in active development. Known limitations include:

- **No encryption at rest** — data is stored in plaintext (use SQLite for local-only setups)
- **No authentication** — assumes trusted local environment
- **Limited input validation** — some edge cases not yet handled
- **No audit logging** — runs/changes are not logged
- **Pandas dataframe limits** — no compression, large datasets may be slow or fail

### Not Suitable For

- **Personal identifiable information (PII)** — no data protection mechanisms
- **HIPAA/GDPR regulated data** — no compliance controls
- **High-volume production ETL** — not designed for 100GB+ datasets
- **Real-time pipelines** — batch-only, no streaming support
- **Multi-user environments** — no auth, permissions, or isolation

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
7. **Review AI-generated code carefully** — verify it does what you expect

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

- **Bugs:** [Open a GitHub Issue](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Questions:** [GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Performance concerns:** Include dataset size, transformation complexity, timing info

**Thank you for helping keep FlowFrame safe and secure.**
