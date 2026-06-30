# FlowFrame Plugin API/SDK

This directory contains FlowFrame's stable public plugin contract. It is the
API/SDK surface intended for plugin developers: manifests, provider interfaces,
registry contracts, node runtime helpers, events, signing helpers, and public
specification models.

The package currently lives inside the backend source tree, but it is kept
self-contained so it can later become an independently published SDK without
changing the runtime architecture today.

## Licensing

This directory, `backend/app/plugin_api/`, is licensed under **Apache-2.0**.
See [LICENSE](LICENSE) for the complete license text.

This Apache-2.0 license applies only to the files in `backend/app/plugin_api/`.
The remainder of FlowFrame is licensed under **AGPL-3.0-only** unless a specific
file or directory states otherwise.

Plugins created using this API may use any license chosen by their authors,
including MIT, Apache-2.0, GPL, AGPL, commercial, proprietary, or another
compatible license. Using the Plugin API does not require plugin authors to
license their plugin under AGPL-3.0.

Official Premium Plugins may be distributed under commercial licenses, and
marketplace plugins use the license selected by their authors.
