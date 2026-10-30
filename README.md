# Unofficial JSM Ops Integration for SecOps SOAR

## Overview

Jira Service Management (JSM) Ops focuses on incident management and IT operations. This unofficial Google SecOps SOAR integration lets playbooks and analysts create, track, acknowledge, assign, close, and escalate JSM Ops alerts, plus look up on-call responders and enrich alerts with notes, tags, and extra properties. A scheduled **Sync Cases** job can close linked JSM Ops alerts when a SecOps case tagged `JSM` is closed.

This integration is owned by the "community". Support Contact: [thecomputercowboy@proton.me](mailto:thecomputercowboy@proton.me).

**Release note:** `JSM Ops v11 - Fix Sync Cases skipping closed cases (status/is_case_closed/tags) and log skip reasons`

## Prerequisites

- A Jira Service Management Cloud site with **Operations** (alerts / on-call) enabled
- An Atlassian user (or eligible account) that can access Ops for your site
- That account’s email address and an Atlassian **API token** (not an OpsGenie GenieKey)
- Your site **Cloud ID** and the Ops **Team ID** used as the default responder

## Configuration setup

This integration calls the JSM Ops REST API at
`https://api.atlassian.com/jsm/ops/api/{cloudId}/v1/...` using HTTP Basic Auth
(`email` + `API token`). That is different from the older OpsGenie-style
Integration Events API, which uses `Authorization: GenieKey {apiKey}` and does
**not** require an email.

### 1. Choose the account that will call the API

Use an Atlassian account that can open Ops / alerts in your JSM site (agent or
admin access to Operations).

- A normal licensed user with Ops access is the most reliable option today.
- An Atlassian **Admin → Directory → Service accounts** identity can work for
  some Atlassian APIs, but Ops REST access for service accounts has historically
  been limited or inconsistent. If Ping returns `401` / `403` with a service
  account, retry with a licensed user email + API token.

The value you enter as **JSM Ops Service Account Email** is simply the email of
the account that owns the API token. It does not have to be a formal Atlassian
“Service account” product object.

### 2. Create an Atlassian API token

1. Sign in as the account from step 1.
2. Open [Manage API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
3. Create an API token (give it a clear name such as `secops-jsm-ops`).
4. Copy the token immediately and store it securely.

Use that token as **JSM Ops API Key** in SecOps.

Do **not** paste an OpsGenie / JSM **integration API key** (GenieKey) into this
field. GenieKey only authenticates
`https://api.atlassian.com/jsm/ops/integration/v2/...` and will produce `401
Unauthorized` against this integration.

Official reference: [Manage API tokens for your Atlassian account](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

### 3. Gather the Cloud ID (tenant info)

The Cloud ID is the UUID for your Atlassian Cloud site (not your site URL and
not your organization ID).

**Option A (fastest):** in a browser, open:

`https://<your-site>.atlassian.net/_edge/tenant_info`

Example response:

```json
{"cloudId":"a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
```

Copy the `cloudId` value into **JSM Ops Cloud ID**.

**Option B:** in [admin.atlassian.com](https://admin.atlassian.com), open your
organization → **Apps** → **Sites** → select the site. The Cloud ID appears in
the URL after `/s/`.

Official reference: [How to find your Atlassian Cloud site’s Cloud ID](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/).

### 4. Gather the Ops Team ID

Create Alert uses the configured Team ID as the default responder and
`visibleTo` target.

1. In JSM, open **Teams** / **Operations** and select the team that should own
   SecOps-created alerts.
2. Copy the team UUID from the team URL or team details page, **or**
3. List teams with the same email + API token + Cloud ID:

```bash
curl --request GET \
  --url 'https://api.atlassian.com/jsm/ops/api/<CLOUD_ID>/v1/teams' \
  --user '<EMAIL>:<API_TOKEN>' \
  --header 'Accept: application/json'
```

Use the returned `teamId` as **JSM Ops Team ID**.

### 5. Verify credentials before configuring SecOps

```bash
curl -s -o /tmp/jsm_ping.json -w "%{http_code}\n" \
  -u '<EMAIL>:<API_TOKEN>' \
  -H 'Accept: application/json' \
  'https://api.atlassian.com/jsm/ops/api/<CLOUD_ID>/v1/alerts?offset=0&size=1'
```

| HTTP status | Meaning |
| ----------- | ------- |
| `200` | Credentials and Cloud ID are valid |
| `401` | Wrong email/token pair, or a GenieKey was used instead of an API token |
| `403` | Authenticated, but the account lacks Ops access |
| `404` | Cloud ID is wrong or the Ops API path is unavailable for that site |

### 6. Configure the SecOps integration instance

After importing the integration ZIP (see Installation):

1. Create or edit the **JSM Ops** instance.
2. Fill in the parameters from the table below.
3. Save, then run **Test** (Ping).

If you previously imported an older package where Cloud ID / email / Team ID
rendered as checkboxes, delete that instance and recreate it after importing
v8+ so the fields refresh as text inputs.

## Authentication

HTTP Basic Auth to the JSM Ops Alerts API:

- Username: Atlassian account email (**JSM Ops Service Account Email**)
- Password: Atlassian API token (**JSM Ops API Key**)
- Tenant: Cloud ID in the URL path (**JSM Ops Cloud ID**)

## Configuration parameters


| Parameter                     | Description                                                                 |
| ----------------------------- | --------------------------------------------------------------------------- |
| JSM Ops API Key               | Atlassian API token for the account email (not a GenieKey / integration key) |
| JSM Ops Cloud ID              | Site Cloud ID UUID from `/_edge/tenant_info`                                |
| JSM Ops Service Account Email | Email of the Atlassian account that owns the API token                      |
| JSM Ops Team ID               | Ops team UUID used as responder / visibility target on Create Alert         |
| Verify SSL                    | Verify SSL certificates when connecting to the API (default: true)          |




## Installation

Install from the packaged ZIP on this repository’s [Releases](https://github.com/The-Computer-Cowboy/Google-SecOps-JSMOps-Integration/releases) page. Do not import a GitHub “Source code” archive; that layout is not a valid SecOps integration package. The import ZIP must have `Integration-JSM Ops.def` at the archive root (the identifier in that filename has to match the integration identifier).

1. Download the latest release ZIP (`JSM-Ops-integration.zip`).
2. In Google SecOps SOAR, open **Response → IDE** and import that ZIP.
3. Complete **Configuration setup** above, then create an Integrations instance with those parameters.
4. Use **Test** (Ping) to validate connectivity. Ping is disabled for playbooks by default.
5. In the IDE, confirm **Sync Cases** appears under this integration (filter by Jobs if needed). Then in **Response → Jobs Scheduler**, create an instance of that job and run it on a short interval (for example every 1–5 minutes).

If job parameters render as checkboxes instead of text fields, re-import the integration and delete/recreate that job instance so it picks up string parameter types (`Type: 2`).

> Note: When exporting from the IDE, confirm the `Managers/` folder is included in the package. Import/export does not always bundle managers automatically. The import ZIP places job definitions in `Jobs/` and job scripts in `JobsScrips/` (SecOps’s folder names).



## Dependencies

- `requests` (typically available on the SecOps SOAR Python runtime)



## Jobs

The **Sync Cases** job uses the **JSM Ops** integration instance credentials (Cloud ID, API token, service account email, Verify SSL). You do not re-enter those on the job; create the integration instance first and run Ping successfully.

### How to create and schedule the job

1. Import the integration ZIP and create a **JSM Ops** instance (see Installation / Configuration setup).
2. In the IDE, confirm **Sync Cases** appears under this integration (filter by Jobs if needed).
3. Open **Response → Jobs Scheduler**.
4. Create a job instance for **Sync Cases**, select the **JSM Ops** integration instance, and fill the job parameters below.
5. Set a short run interval (for example every 1–5 minutes; the packaged default is 300 seconds).
6. Enable the job and run it once manually to confirm logs look healthy.

Playbooks that create JSM alerts must set **Alias** to `secops-case-[Case.Id]` (preferred) or `[Case.Id]`. Sync Cases matches SecOps cases to JSM alerts through that alias. Without it, Sync Cases cannot find the alert to close.

---

### Sync Cases

One-way job from Google SecOps to JSM Ops. It **only** looks at SecOps cases with the configured tag (default: `JSM`). Open JSM alerts never create, update, or close SecOps cases.

When a tagged SecOps case is closed and the linked JSM Ops alert is still open, the job:

1. Resolves the JSM Ops alert by alias (`secops-case-{caseId}`, then the raw case ID).
2. Adds a note with the SecOps case title, close reason, root cause, and close comment.
3. Closes the JSM Ops alert.

#### What you need to configure

| Requirement | What to do |
| ----------- | ---------- |
| Integration instance | Working **JSM Ops** instance (Ping succeeds). The job reads Cloud ID / API token / email from it. |
| Case tag on SecOps cases | Tag every case that should sync (default tag: `JSM`). Untagged cases are ignored. Set the same value in the job’s **Case Tag** parameter. |
| Linked JSM alert + alias | Playbooks must create the JSM alert (for example with **Create Alert**) and set Alias to `secops-case-[Case.Id]` or `[Case.Id]`. |
| Job Scheduler instance | Create a **Sync Cases** job, bind it to the JSM Ops instance, set parameters, enable, and schedule. |
| Lookback / throughput | **Hours Backwards** and **Max Cases Per Run** control how far back closed cases are scanned and how many are processed per run. Raise them if closures are missed; keep them modest if runs are slow. |
| Environment scope (optional) | Leave **Environment** empty for all SecOps environments, or pass a comma-separated list to limit the sync. |

#### Job parameters

| Parameter | Required | Description |
| --------- | -------- | ----------- |
| Case Tag | Yes | Only cases with this tag are synced. Default: `JSM`. |
| Hours Backwards | Yes | How far back to look for recently closed SecOps cases, in hours. Default: `24`. |
| Max Cases Per Run | Yes | Cap on tagged closed cases processed per run. Default: `50`. |
| Environment | No | Optional comma-separated SecOps environment names. Empty = all environments. |

#### Typical values

- Case Tag: `JSM`
- Hours Backwards: `24` (or slightly larger than your schedule gap if jobs can pause)
- Max Cases Per Run: `50`
- Environment: empty (unless you only want specific environments)

## Actions



### Ping

Verifies connectivity and credentials. Disabled by default; used by Content Hub **Test**. Script result: `is_success` (`true` / `false`).

### Create Alert

Creates a JSM Ops alert for your team.

**Mandatory fields**

- Alert Message
- Alert Title
- Alert Priority (`P0`–`P5`)

**Optional fields**

- Alert Tag (comma-separated tags)
- Alias (deduplication key; use `secops-case-[Case.Id]` so Sync Cases can match the alert)
- Source (for example `Google SecOps`)
- Details (JSON object string of extra detail fields)

JSON sample: `[Examples/Create Alert.json](Examples/Create%20Alert.json)`

### Get Request Status

Tracks asynchronous write requests (Create / Close / Escalate / Acknowledge / Assign / similar) and returns alert details when available.

**Mandatory fields**

- Request ID (returned by async write actions)

JSON sample: `[Examples/Get Request Status.json](Examples/Get%20Request%20Status.json)`

### Get Alert

Retrieves full alert details by Alert ID (status, priority, owner, tags, responders, and more).

**Mandatory fields**

- Alert ID

JSON sample: `[Examples/Get Alert.json](Examples/Get%20Alert.json)`

### Get Alert by Alias

Retrieves an alert using its alias (useful when Create Alert used a SecOps case/alert ID as the alias).

**Mandatory fields**

- Alias

JSON sample: `[Examples/Get Alert by Alias.json](Examples/Get%20Alert%20by%20Alias.json)`

### List Alerts

Lists alerts with optional query filtering and pagination. Useful to check for existing open alerts before creating a new one.

**Optional fields**

- Query
- Size (default `20`)
- Offset (default `0`)

JSON sample: `[Examples/List Alerts.json](Examples/List%20Alerts.json)`

### Acknowledge Alert

Acknowledges an alert so responders know it is being handled and escalations stop.

**Mandatory fields**

- Alert ID

JSON sample: `[Examples/Acknowledge Alert.json](Examples/Acknowledge%20Alert.json)`

### Add Alert Note

Adds a note to an alert (case links, enrichment summaries, investigation updates).

**Mandatory fields**

- Alert ID
- Note

JSON sample: `[Examples/Add Alert Note.json](Examples/Add%20Alert%20Note.json)`

### Assign Alert

Assigns an alert to a user by Atlassian account ID.

**Mandatory fields**

- Alert ID
- Account ID

JSON sample: `[Examples/Assign Alert.json](Examples/Assign%20Alert.json)`

### Add Responder

Adds a team, user, escalation, or schedule responder to an alert.

**Mandatory fields**

- Alert ID
- Responder ID
- Responder Type (`team` / `user` / `escalation` / `schedule`)

JSON sample: `[Examples/Add Responder.json](Examples/Add%20Responder.json)`

### Update Priority

Updates alert priority (`P0`–`P5`).

**Mandatory fields**

- Alert ID
- Priority

JSON sample: `[Examples/Update Priority.json](Examples/Update%20Priority.json)`

### Add Tags

Adds one or more tags to an alert.

**Mandatory fields**

- Alert ID
- Tags (comma-separated)

JSON sample: `[Examples/Add Tags.json](Examples/Add%20Tags.json)`

### Add Extra Properties

Adds custom key/value properties to an alert.

**Mandatory fields**

- Alert ID
- Extra Properties (JSON object string)

JSON sample: `[Examples/Add Extra Properties.json](Examples/Add%20Extra%20Properties.json)`

### Close Alert

Closes a JSM Ops alert by Alert ID (usually from Get Request Status after Create Alert, or from Get Alert / Get Alert by Alias).

**Mandatory fields**

- Alert ID

JSON sample: `[Examples/Close Alert.json](Examples/Close%20Alert.json)`

### Escalate Alert

Triggers an escalation policy for an alert.

**Mandatory fields**

- Alert ID
- Escalation ID

JSON sample: `[Examples/Escalate Alert.json](Examples/Escalate%20Alert.json)`

### Get On-Call

Lists current on-call responders for a schedule. Optionally evaluate on-call at a specific ISO-8601 date/time.

**Mandatory fields**

- Schedule ID

**Optional fields**

- Date (ISO-8601; omit for now)

JSON sample: `[Examples/Get On-Call.json](Examples/Get%20On-Call.json)`

## License

Copyright 2026 The-Computer-Cowboy

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

