# SPDX-License-Identifier: AGPL-3.0-only
"""In-process tools the assistant uses to read the catalog and data shape and to propose edits.

Tools receive turn-local references (``n0`` nodes, ``d0`` datasets, ``c0`` columns), never
row values, and return plain dictionaries.
"""
