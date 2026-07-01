# Ciaren Brand Guidelines

These guidelines help contributors, plugin authors, educators, and community
members present Ciaren consistently without creating confusion about what is
official.

## Name

Use `Ciaren` with capital `F`s.

Correct:

- Ciaren
- Ciaren Core
- Ciaren Plugin API
- Plugin for Ciaren

Avoid:

- Ciaren
- Flow Frame
- ciaren as a product name, except in package names or commands where
  lowercase is conventional

## Describing Ciaren

Preferred short description:

> Ciaren is a local-first visual platform for building data and ML workflows
> and exporting readable pandas or polars Python.

For longer descriptions, emphasize:

- Local-first execution
- Visual workflow building
- Readable Python export
- Plugin-first extensibility
- Open-source core with a public Plugin API/SDK

Avoid presenting Ciaren as:

- A hosted SaaS product by default
- A replacement for Airflow, dbt, Spark, or warehouse-scale orchestration
- A production-certified or independently audited security product

## Logos and Visuals

Use official logo assets from the repository when available. Do not use the logo
as the primary identity for a third-party company, hosted service, plugin
marketplace, or paid product.

When showing a third-party integration, keep your own brand visually primary and
use Ciaren only to indicate compatibility.

## Official vs Community

Use clear labels:

- `Official` means published, maintained, or explicitly endorsed by the Ciaren
  maintainers.
- `Community` means created by contributors or third parties.
- `Compatible with Ciaren` means it works with Ciaren, but is not
  necessarily reviewed or endorsed.

Good examples:

- `Acme Connector for Ciaren`
- `Community template for Ciaren`
- `Compatible with Ciaren`

Avoid:

- `Official Ciaren Connector` unless it is official
- `Ciaren Cloud` for an unaffiliated hosted service
- `Ciaren Marketplace` for a third-party marketplace unless approved

## Plugins

Plugin authors may choose their own licenses and branding. To avoid confusion:

- Put your organization or plugin name first.
- Say `for Ciaren` or `compatible with Ciaren`.
- Include a clear disclaimer if the plugin is not official.

Example:

> Acme Snowflake Connector for Ciaren is a third-party plugin and is not
> affiliated with or endorsed by the Ciaren maintainers.

## Security and Maturity Language

Ciaren is alpha software and has not yet completed a formal independent
third-party security audit. State that plainly when relevant, then point users to
the controls they should use: local-first deployment, `CIAREN_API_TOKEN`,
trusted network boundaries, representative testing, and their own review for
sensitive environments.

Avoid alarmist language. Prefer:

> Ciaren is alpha software. For sensitive or production workflows, review the
> security notes and validate the deployment against your own requirements.

## Questions

When in doubt, ask in GitHub Discussions before publishing branding that could
look official.
