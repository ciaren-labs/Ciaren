"""An example Ciaren plugin.

Demonstrates a data-quality / validator node: it checks that a column's values
satisfy a rule (regex pattern or allowed-value set) and adds a boolean pass/fail
column. It depends only on the plugin contract (``app.plugin_api``) and pandas.
"""

from ciaren_validator.plugin import ValidatorPlugin

__all__ = ["ValidatorPlugin"]
