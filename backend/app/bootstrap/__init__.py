# SPDX-License-Identifier: AGPL-3.0-only
"""Application bootstrap: startup/shutdown lifecycle, one-time seeding, and the
built-in frontend mount. Kept out of ``app.main`` so ``create_app()`` stays a short
composition and each concern can be tested in isolation."""
