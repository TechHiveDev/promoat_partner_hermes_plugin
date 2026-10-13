# Promoat for Hermes

Native Hermes plugin for the Promoat Partner API. It calls the MCP server at `https://platform.promoat.ai/mcp` with the user's own `PROMOAT_KEY`. It does not charge, reserve, or refund on its own. `PROMOAT_BASE_URL` overrides the site host; the plugin always appends `/mcp`.

## Install from this repo

The plugin files sit at the repository root.

```bash
hermes plugins install TechHiveDev/promoat_partner_hermes_plugin
```

Hermes asks for `PROMOAT_KEY` at install and stores it outside this package. Do not commit a key.

Check the folder before installing:

```bash
hermes plugins doctor . --ci
hermes plugins validate .
python -m unittest test_tools.py
```

## MCP server instead of this plugin

Paste this into Hermes `config.yaml`. The key stays in the profile `.env` as `PROMOAT_KEY`.

```yaml
mcp_servers:
  promoat:
    url: https://platform.promoat.ai/mcp
    headers:
      Authorization: "Bearer ${PROMOAT_KEY}"
    trust: untrusted
```

`trust: untrusted` makes Hermes ask before any tool that is not marked read-only.
