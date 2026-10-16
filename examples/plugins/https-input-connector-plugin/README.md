# HTTPS Input Connector Plugin - example Ciaren plugin

A read-only connector plugin that downloads one HTTPS CSV or JSON document and
returns it as a DataFrame through Ciaren's SQL Input node.

## What it shows

- A `Plugin` that registers a `ConnectorProvider`.
- A read-only `ConnectorRuntime` with `test`, `list_tables`, and `read`.
- A connector `config_schema` for URL, format, timeout, and streamed byte limit.
- A manifest that declares the `network` permission.
- SSRF-aware URL handling implemented inside the plugin with the standard
  library: HTTPS-only, resolved-address checks, no automatic redirects, timeout,
  and streamed response-size enforcement.

## Security behavior

The connector rejects non-HTTPS URLs, URL credentials, and hosts that resolve to
private, loopback, link-local, or reserved addresses. Redirect responses are not
followed automatically; if a response includes a `Location`, the plugin validates
that target and still refuses the redirect.

## Try it

Point Ciaren at the parent directory:

```bash
export CIAREN_PLUGINS_DIR=/path/to/examples/plugins
ciaren serve
```

After approval, create an **HTTPS CSV/JSON** connection with:

- `url`: a direct `https://` URL.
- `format`: `csv` or `json`.
- `max_bytes`: maximum streamed response size.
- `timeout_seconds`: request timeout.

Use SQL Input with the `download` table. The connector ignores SQL queries; it is
intended as a compact example of a safe, read-only HTTPS input connector.

## Signed `.ciarenplugin` package

Rebuild the package after editing the plugin with:

```bash
python examples/plugins/build_https_input_ciarenplugin.py
```

Trust the demo key, then verify and install:

```bash
export CIAREN_TRUSTED_PLUGIN_KEYS='{"ciaren-demo": "b827f3795467a701b018a0d57ab5900af43669d3622340905559d86ae2ec4bdd"}'

ciaren-plugin verify  examples/plugins/dist/community.https-input-0.1.0-alpha.1.ciarenplugin
ciaren-plugin install examples/plugins/dist/community.https-input-0.1.0-alpha.1.ciarenplugin --trusted
```

The demo signing key is committed only so contributors can reproduce the example
package. Real publishers should generate and protect their own key.

