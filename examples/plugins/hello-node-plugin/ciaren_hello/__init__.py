"""An example Ciaren plugin.

Demonstrates the smallest possible plugin: it contributes one catalog node and
declares a capability. It depends only on the plugin contract (``app.plugin_api``,
which will be published as ``ciaren-plugin-api``) — never on Ciaren's
private internals.
"""

from ciaren_hello.plugin import HelloPlugin

__all__ = ["HelloPlugin"]
