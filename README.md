# Nottinghamshire Gritting for Home Assistant

A Home Assistant custom integration that answers a practical question: **is gritting expected on Nottinghamshire's roads overnight?**

## Source priority

The integration combines three sources, in strict priority order:

1. **Nottinghamshire County Council winter-service email — confirmed**
   - Highest priority when a current County decision is available.
2. **Nottingham City Council Daily Gritting Update — inferred proxy**
   - The most useful day-to-day fallback because it publishes a specific **Today's Gritting Action** such as **Gritting Required**, **No Gritting Required**, **Gritting Tonight** or **No Gritting Tonight**.
   - Either outcome can drive the binary sensor, but the source remains explicitly marked as an inferred City proxy for the wider county.
   - The GREEN / AMBER / RED colour is not used as the gritting decision because Nottingham City states that the colour describes the weather forecast and does not necessarily indicate whether gritting is required.
3. **Nottinghamshire County Council @NottsCC on X — confirmed when current**
   - Kept as a fallback/context source.
   - Useful when the County posts an explicit same-night treatment decision.
   - Broad wording about cold conditions continuing over several days is not carried forward as a nightly gritting decision.

A current higher-priority source wins over a lower-priority one.

## X feed implementation

X does not provide a practical keyless profile API for this use. Version 0.2.0/0.2.1 used X's embedded-timeline syndication endpoint, but that endpoint repeatedly returned **HTTP 429** from Home Assistant and even in a normal browser.

From **0.2.2**, the integration instead uses the documented public FxTwitter/FxEmbed v2 profile-timeline API:

`https://api.fxtwitter.com/2/profile/NottsCC/statuses?count=100`

FxTwitter is a **third-party bridge to public X data**; it is not operated by Nottinghamshire County Council or X. It requires no account, developer key or API token. Its published v2 rate limit is 1000 requests/minute per IP, while this integration makes only one request every 30 minutes.

The underlying post remains an official @NottsCC post and its original X URL is exposed as `source_url`. The bridge itself is deliberately treated as **best effort**: if it times out, rate-limits or changes format, the integration falls through to County email and then the Nottingham City positive proxy rather than making the sensor fail.

The binary sensor and status sensor expose:
- `source`
- `source_key`
- `confidence`
- `source_url`
- `x_feed_available`
- `x_last_check`
- `x_last_success`
- `x_last_error`
- `x_latest_post_time`
- `x_latest_post_text`
- `x_latest_post_url`
- `x_latest_gritting_post_time`
- `x_latest_gritting_post_text`
- `x_latest_gritting_post_url`
- `x_latest_gritting_post_planned`

## Entities

- `binary_sensor.gritting_overnight`
  - **On** — current County gritting decision, or City daily proxy says gritting is required.
  - **Off** — current County decision says no treatment, or City daily proxy says no gritting is required.
  - **Unknown** — no current recognised nightly decision (including after 09:00 expiry); the entity remains available. This does not mean “Not planned”.
- `sensor.gritting_status`
  - `Planned`
  - `Not planned`
  - `Likely — City says grit`
  - `Likely not — City says no grit`
  - `Awaiting decision`
  - `Decision unclear`
- `sensor.minimum_road_temperature`
- `sensor.treatment_time`
- `sensor.last_decision` — timestamp of the effective current decision.

All five entities remain available while awaiting a decision. Temperature, treatment time and last decision report **unknown** when no current value exists, including when a current bulletin omits a field. Source and X diagnostics remain accessible as attributes of the status and binary sensors; source fields are empty without a current decision, while X diagnostics retain their independently tracked values. A best-effort X fetch failure is reported by `x_feed_available` and `x_last_error` and does not make working email-based entities unavailable. Missing or expired decisions are not integration failures.

## Why use the County X feed?

Nottinghamshire County Council says Via East Midlands makes the daily gritting decision using specialist road-surface forecasts, ice-prediction software and roadside weather stations. The County's gritting information specifically directs residents to follow **@NottsCC** for gritting updates.

Official information:
- https://www.nottinghamshire.gov.uk/transport/gritting/about
- https://www.nottinghamshire.gov.uk/transport/gritting/map

## Installation

### HACS

1. Open **HACS → ⋮ → Custom repositories** in Home Assistant.
2. Enter `https://github.com/markxroberts/nottinghamshire_gritting`, select **Integration**, and choose **Add**.
3. Open **Nottinghamshire Gritting** in HACS and select **Download**.
4. Restart Home Assistant. For a first installation, open **Settings → Devices & services → Add integration** and select **Nottinghamshire Gritting**.

### Manual installation

Copy `custom_components/nottinghamshire_gritting` into `/config/custom_components/`, then follow step 4 above.

### Email decision sources

For County and Nottingham City email support:

1. Configure Home Assistant's **IMAP** integration for the mailbox receiving the winter-service bulletins.
2. In the IMAP options, enable **message text**, so `imap_content` events contain the email body.
3. Subscribe to the relevant official winter-service bulletins.

New messages are processed immediately from `imap_content` events. From 0.2.5, the integration also performs a short **startup recovery scan** of the last two days of mail using Home Assistant's existing IMAP connection settings. This means a current City/County bulletin that arrived before a Home Assistant restart or integration reload is recovered rather than being lost until the next email arrives. The recovery runs in the background and scans only the newest 60 messages in the recent window.

## Decision expiry

A decision received at or after 09:00 remains current until **09:00 the following morning**. An early-morning update received before 09:00 belongs to the night just ending and expires at 09:00 that same morning. A decision from yesterday therefore remains valid after midnight, but is expired at 09:00 rather than being incorrectly shown as tonight's decision during the following day.

## Source behaviour

### Nottinghamshire County email

A current explicit County decision is authoritative and takes priority over the proxy sources.

### Nottingham City Daily Gritting Update

The City bulletin is designed as a daily operational update and includes a **Today's Gritting Action** field. The parser recognises both positive and negative action wording, including:

- “Gritting Required”
- “No Gritting Required”
- “Gritting Tonight”
- “No Gritting Tonight”

The GREEN / AMBER / RED headline is retained only as context; it does not itself switch the binary sensor.

Because Nottingham City is a separate highway authority, its decision is still labelled `confidence: inferred` when used as a proxy for Nottinghamshire County.

### County X

@NottsCC remains useful when it publishes a specific same-night decision such as “Gritters will be out from 7.30pm”. A previous night's post, or general wording that cold conditions will continue through the weekend, does not automatically make subsequent nights ON.

## Logging

For temporary diagnostics:

```yaml
logger:
  logs:
    custom_components.nottinghamshire_gritting: debug
```

## Tests

With Home Assistant, its IMAP dependency (`aioimaplib`), pytest and pytest-asyncio installed in a compatible Python environment, run `python -m pytest -q`.

## Version history

### 0.2.6

- Keep entities available between the unchanged 09:00 decision expiry and the next update.
- Report `Awaiting decision` on the status sensor and unknown on the binary sensor when no current decision exists; an unrecognised decision also leaves the binary state unknown.
- Report unknown instead of unavailable for missing current temperature, treatment time and decision time.
- Preserve source/X diagnostic attributes, source priority and explicit planned/not-planned states.
- Add regression tests for expiry, startup, unclear decisions, missing fields and X failure diagnostics.

### 0.2.5

- Added startup/reload IMAP recovery for current Nottingham City and Nottinghamshire County gritting bulletins already present in the mailbox.
- Searches only the last two days and the newest 60 messages, then reuses the existing City/County parser and source priority.
- Uses Home Assistant's configured IMAP connection without storing or exposing separate mailbox credentials.
- Keeps the normal `imap_content` event path for new bulletins.

### 0.2.4

- Reordered source priority to County email → Nottingham City Daily Gritting Update → County X.
- Nottingham City daily **Gritting Required / No Gritting Required** decisions can now set the proxy binary sensor either ON or OFF.
- Added explicit parsing for the City's **Today's Gritting Action** field and **Gritting Tonight / No Gritting Tonight** wording.
- Kept City GREEN / AMBER / RED as weather context only; the colour does not itself determine the gritting state.
- Demoted broad County X posts to fallback/context so multi-day cold-weather wording does not obscure the more useful daily City decision.

### 0.2.3

- Increased the @NottsCC timeline depth from 20 to 100 posts so a gritting update is less likely to scroll out of the first page before the overnight decision expires.
- Added diagnostics showing the newest @NottsCC post and the newest gritting-related @NottsCC post, including its text, timestamp, URL and whether the parser considered it an explicit gritting decision.
- Retains the rule that retrospective wording such as “gritters have been out” is not treated as a plan for the coming night.
- Nottingham City Amber/Green/Red weather colour alone does not switch the gritting binary sensor because the City winter-service plan states that the colour is not itself an indication that treatment is required.

### 0.2.2

- Replaced X's rate-limited embedded-timeline syndication endpoint with the documented public FxTwitter/FxEmbed v2 profile timeline.
- Kept @NottsCC as the preferred decision source while making the third-party transport explicit in the source label.
- Retains County email and Nottingham City positive-proxy fallbacks if the X bridge is unavailable.
- Bumped the manifest so HACS/Home Assistant can distinguish this build from 0.2.1.

### 0.2.1

- Packaged the integration for HACS custom repository installation.

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
