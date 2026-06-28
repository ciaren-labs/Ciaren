"""An example FlowFrame plugin.

Demonstrates the smallest possible plugin: it contributes one catalog node and
declares a capability. It depends only on the plugin contract (``app.plugin_api``,
which will be published as ``flowframe-plugin-api``) — never on FlowFrame's
private internals.
"""

from flowframe_hello.plugin import HelloPlugin

__all__ = ["HelloPlugin"]
