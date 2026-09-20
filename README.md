# Nottinghamshire Gritting for Home Assistant

A small Home Assistant custom integration which turns Nottinghamshire County Council's official **Winter Service and Gritting information** email updates into Home Assistant entities.

## Entities

- `binary_sensor.gritting_overnight` — **On** when the latest current council update says gritting/treatment is planned; **Off** when it explicitly says no treatment is planned; **Unavailable** while waiting for a new decision or if a message cannot be interpreted safely.
- `sensor.gritting_status` — `Planned`, `Not planned`, `Awaiting decision`, or `Decision unclear`.
- `sensor.minimum_road_temperature` — road-surface temperature quoted in the update, when present.
- `sensor.treatment_time` — first treatment time parsed from the update, when present.
- `sensor.last_decision` — timestamp of the last relevant council update (diagnostic).

The binary sensor also carries attributes including the source subject, sender, decision time, treatment time, minimum road temperature and a short excerpt from the council message.

## Why email rather than weather inference?

Nottinghamshire says Via makes the daily winter-service decision using specialist road forecasting, ice-prediction software and roadside weather stations. The published decision is therefore a better source than trying to infer gritting from an ordinary local air-temperature sensor.

Official information:
- https://www.nottinghamshire.gov.uk/transport/gritting/map
- https://www.nottinghamshire.gov.uk/council-and-democracy/news-and-media/emailme/newsletter-topics

## Installation

1. Copy the included `custom_components/nottinghamshire_gritting` folder into your Home Assistant `/config/custom_components/` directory.
2. Restart Home Assistant.
3. Subscribe the mailbox you intend to monitor to Nottinghamshire County Council's **Winter Service and Gritting information** e-bulletin:
   https://www.nottinghamshire.gov.uk/council-and-democracy/news-and-media/emailme/newsletter-topics
4. Add/configure Home Assistant's **IMAP** integration for that mailbox.
5. In the IMAP integration options, enable **message text** so `imap_content` events include the email body. Home Assistant only includes `text` when this option is selected.
6. Preferably use an IMAP folder or search that contains only the Nottinghamshire winter-service messages. This reduces event traffic and eliminates the chance of unrelated email matching.
7. Go to **Settings → Devices & services → Add integration**, search for **Nottinghamshire Gritting**, and add it.

Home Assistant IMAP documentation:
https://www.home-assistant.io/integrations/imap/

## Decision expiry

A decision received today is treated as current until **09:00 the following morning**. A decision received yesterday therefore still describes the overnight period after midnight, but it is deliberately expired at 09:00 rather than being incorrectly shown as tonight's decision all day.

If a new relevant council message is received but its wording cannot be safely classified, the integration reports **Decision unclear** and makes the binary sensor unavailable rather than guessing.

## First winter update

The parser deliberately recognises several common forms such as:

- “Gritters will be out ...”
- “Gritting/treatment is planned ...”
- “Next scheduled run ...”
- “No gritting/treatment is planned ...”
- “No action required ...”

The exact GovDelivery wording can change. If the first real 2026/27 Nottinghamshire message produces `Decision unclear`, copy its subject/body from Home Assistant's event listener or the email itself and the parser can be adjusted very easily.

## Logging

To temporarily enable parser diagnostics:

```yaml
logger:
  logs:
    custom_components.nottinghamshire_gritting: debug
```

## Version

0.1.2 — fixes Home Assistant thread-safety warning when entities refresh on the hourly expiry check.

0.1.0 — initial release, targeted at Home Assistant 2026.9.x.


## 0.1.2

- Added local Home Assistant brand icon/logo.
- Added state-aware icon translations for the Gritting overnight binary sensor.
