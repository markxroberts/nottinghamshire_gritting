# Nottinghamshire Gritting for Home Assistant

A Home Assistant custom integration that answers a practical question: **is gritting expected on Nottinghamshire's roads overnight?**

## Source priority

Version 0.2.0 combines three sources, in strict priority order:

1. **Nottinghamshire County Council @NottsCC on X — confirmed**
   - Preferred source.
   - The County's own gritting page tells residents to follow @NottsCC to find out when Nottinghamshire roads are being gritted.
   - The integration polls the public X syndication timeline every 30 minutes and once immediately after startup.
2. **Nottinghamshire County Council winter-service email — confirmed**
   - Used when a current County email decision is available and there is no current X decision.
3. **Nottingham City Council winter-service email — inferred proxy**
   - Used only as a positive fallback when the City explicitly says it is gritting.
   - A City "no grit" decision is deliberately ignored because road conditions elsewhere in Nottinghamshire can be colder.
   - The status is shown as **Likely — Nottingham City proxy**, never as a confirmed County decision.

A stronger source always wins over a weaker one.

## X feed implementation

X does not provide a free RSS feed for profiles. The integration therefore uses the public profile-syndication endpoint that X itself uses for embedded timelines:

`https://syndication.twitter.com/srv/timeline-profile/screen-name/NottsCC`

No X account, developer key or API token is required.

This endpoint is not a documented API and can return HTTP 429 or change format. For that reason it is treated as **best effort**. If it is unavailable, the integration falls through to County email and then the Nottingham City positive proxy instead of making the sensor fail.

The binary sensor and status sensor expose:
- `source`
- `source_key`
- `confidence`
- `source_url`
- `x_feed_available`
- `x_last_check`
- `x_last_success`
- `x_last_error`

## Entities

- `binary_sensor.gritting_overnight`
  - **On** — confirmed County gritting, or positive Nottingham City proxy when no County decision is available.
  - **Off** — only when a current County source explicitly says treatment is not planned.
  - **Unavailable** — no current usable decision.
- `sensor.gritting_status`
  - `Planned`
  - `Not planned`
  - `Likely — Nottingham City proxy`
  - `Awaiting decision`
  - `Decision unclear`
- `sensor.minimum_road_temperature`
- `sensor.treatment_time`
- `sensor.last_decision` — timestamp of the effective current decision.

## Why use the County X feed?

Nottinghamshire County Council says Via East Midlands makes the daily gritting decision using specialist road-surface forecasts, ice-prediction software and roadside weather stations. The County's gritting information specifically directs residents to follow **@NottsCC** for gritting updates.

Official information:
- https://www.nottinghamshire.gov.uk/transport/gritting/about
- https://www.nottinghamshire.gov.uk/transport/gritting/map

## Installation

1. Copy `custom_components/nottinghamshire_gritting` into Home Assistant's `/config/custom_components/` directory, or update it through your normal custom-integration/HACS workflow.
2. Restart Home Assistant.
3. Add **Nottinghamshire Gritting** from **Settings → Devices & services** if it is not already configured.

### Optional email fallbacks

For County and Nottingham City email fallback support:

1. Configure Home Assistant's **IMAP** integration for the mailbox receiving the winter-service bulletins.
2. In the IMAP options, enable **message text**, so `imap_content` events contain the email body.
3. Subscribe to the relevant official winter-service bulletins.

The integration works without IMAP if the @NottsCC X source is available.

## Decision expiry

A decision received today remains current until **09:00 the following morning**. A decision from yesterday therefore remains valid after midnight, but is expired at 09:00 rather than being incorrectly shown as tonight's decision during the following day.

## Source behaviour

### County X or County email

An explicit positive or negative operational decision is authoritative.

Examples the parser recognises include:
- “Gritters will be out ...”
- “Our gritters are heading out ...”
- “We'll be gritting ...”
- “Gritting/treatment is planned ...”
- “Routes will be treated ...”
- “No gritting/treatment is planned ...”
- “We won't be gritting ...”
- “No action required ...”

### Nottingham City email

Only a **positive** City treatment decision is used as a proxy. It can make the binary sensor **On** with `confidence: inferred`, but it can never switch the County sensor **Off**.

## Logging

For temporary diagnostics:

```yaml
logger:
  logs:
    custom_components.nottinghamshire_gritting: debug
```

## Version history

### 0.2.0

- Added @NottsCC X timeline as the preferred confirmed source.
- Added automatic 30-minute X polling and startup refresh.
- Added Nottingham City winter-service email as a positive-only fallback proxy.
- Added source priority, confidence and source URL attributes.
- Added X availability/last-success/error diagnostics.
- Preserved County email as the confirmed secondary source.
- Migrates the existing v0.1.x stored County email decision automatically.

### 0.1.2

- Added local Home Assistant brand icon/logo.
- Added state-aware icon translations for the Gritting overnight binary sensor.
- Fixed Home Assistant thread-safety warning when entities refresh on the hourly expiry check.

### 0.1.0

- Initial release.
