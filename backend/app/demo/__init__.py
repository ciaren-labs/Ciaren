"""Built-in demo project seeding.

On first server boot (gated by ``settings.SEED_DEMO``) the FastAPI lifespan
calls :func:`seed_demo`, which creates a ``Demo`` project populated with four
small, deliberately messy sample datasets and a handful of example flows of
increasing complexity. The whole thing is deterministic (fixed RNG seed) and
idempotent: it is a no-op once the Demo project exists.
"""

from app.demo.seed import DEMO_PROJECT_NAME, seed_demo

__all__ = ["DEMO_PROJECT_NAME", "seed_demo"]
