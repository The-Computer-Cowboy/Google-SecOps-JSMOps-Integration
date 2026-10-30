import json
import time

from SiemplifyJob import SiemplifyJob
from JSMOpsManager import JSMOpsManager


INTEGRATION_NAME = "JSM Ops"
SCRIPT_NAME = "Sync Cases"
ALIAS_PREFIX = "secops-case-"
CONTEXT_KEY = "jsm_ops_sync_state"


def _to_bool(value, default=True):
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _to_int(value, default, param_name):
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        raise Exception("{} must be an integer. Received: {}".format(param_name, value))


def _hours_back_ms(hours):
    return int((time.time() - (hours * 3600)) * 1000)


def _parse_csv(raw_value):
    if not raw_value or not str(raw_value).strip():
        return []
    return [item.strip() for item in str(raw_value).split(",") if item.strip()]


def _job_param(siemplify, name, default=""):
    return siemplify.extract_job_param(
        param_name=name,
        default_value=default,
        is_mandatory=False,
        print_value=True,
    )


def _config_param(siemplify, config, name, default=""):
    if config and config.get(name) not in (None, ""):
        return config.get(name)
    return siemplify.extract_configuration_param(
        provider_name=INTEGRATION_NAME,
        param_name=name,
        default_value=default,
    )


def _load_state(siemplify):
    try:
        raw = siemplify.get_scoped_job_context_property(CONTEXT_KEY)
    except Exception:
        raw = None
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _save_state(siemplify, state):
    siemplify.set_scoped_job_context_property(CONTEXT_KEY, json.dumps(state))


def _case_state(state, case_id):
    entry = state.get(str(case_id))
    if not isinstance(entry, dict):
        entry = {}
        state[str(case_id)] = entry
    return entry


def _alias_for_case(case_id):
    return "{}{}".format(ALIAS_PREFIX, case_id)


def _normalize_case_ids(raw):
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = (
            raw.get("cases")
            or raw.get("case_ids")
            or raw.get("ids")
            or raw.get("values")
            or list(raw.values())
        )
    if not isinstance(raw, list):
        raw = [raw]
    ids = []
    for item in raw:
        if isinstance(item, dict):
            case_id = item.get("id") or item.get("identifier") or item.get("case_id")
            if case_id is not None:
                ids.append(str(case_id))
        elif item is not None:
            ids.append(str(item))
    return ids


def _collect_closed_case_ids(siemplify, tag, hours_back, max_cases, environments):
    ids = []
    seen = set()

    def add(raw):
        for case_id in _normalize_case_ids(raw):
            if case_id not in seen:
                seen.add(case_id)
                ids.append(case_id)

    env_arg = environments or None
    since_ms = _hours_back_ms(hours_back)

    try:
        add(
            siemplify.get_cases_by_filter(
                tags=[tag],
                environments=env_arg,
                start_time_unix_time_in_ms=since_ms,
            )
        )
    except Exception as e:
        siemplify.LOGGER.warn("get_cases_by_filter(tags={}) failed: {}".format(tag, e))

    kwargs = {
        "status": "CLOSE",
        "close_time_from_unix_time_in_ms": since_ms,
        "max_results": min(max(max_cases, 100) * 4, 10000),
    }
    try:
        try:
            add(siemplify.get_cases_ids_by_filter(tags=[tag], **kwargs))
        except TypeError:
            add(siemplify.get_cases_ids_by_filter(**kwargs))
    except Exception as e:
        siemplify.LOGGER.info("get_cases_ids_by_filter(CLOSE) skipped: {}".format(e))

    return ids


def _get_case(siemplify, case_id):
    try:
        case = siemplify._get_case_by_id(case_id)
    except Exception:
        case = siemplify._get_case_by_id([case_id])
    if isinstance(case, list):
        case = case[0] if case else None
    if isinstance(case, dict):
        nested = case.get("case") or case.get("Case")
        if isinstance(nested, dict):
            return nested
    return case


def _case_field(case, *names, default=None):
    for name in names:
        if isinstance(case, dict) and name in case and case.get(name) not in (None, ""):
            return case.get(name)
    return default


def _case_closed_detail(case):
    """Return (is_closed, detail) for logging.

    Current CaseFullDetails uses OPENED=1, CLOSED=2. Prefer is_case_closed when
    present. Do not treat status 1 as closed (that falsely matches open cases).
    """
    if not isinstance(case, dict):
        return False, "case payload is not a dict"

    for flag_name in ("is_case_closed", "isCaseClosed", "IsCaseClosed"):
        if flag_name in case and case.get(flag_name) not in (None, ""):
            flag = case.get(flag_name)
            if isinstance(flag, bool):
                return flag, "{}={}".format(flag_name, flag)
            text = str(flag).strip().lower()
            if text in ("true", "yes"):
                return True, "{}={!r}".format(flag_name, flag)
            if text in ("false", "no"):
                return False, "{}={!r}".format(flag_name, flag)

    status = _case_field(case, "status", "Status", "caseStatus", "case_status")
    if status is None:
        return False, "no status/is_case_closed fields"
    if isinstance(status, str):
        upper = status.strip().upper()
        if upper in ("CLOSE", "CLOSED"):
            return True, "status={!r}".format(status)
        if upper in ("OPEN", "OPENED"):
            return False, "status={!r}".format(status)
        if upper.isdigit():
            status = int(upper)
        else:
            return False, "status={!r} (unrecognized)".format(status)
    try:
        status_int = int(status)
    except (TypeError, ValueError):
        return False, "status={!r} (unrecognized)".format(status)
    if status_int in (0, 1):
        return False, "status={} (OPENED)".format(status_int)
    if status_int == 2:
        return True, "status=2 (CLOSED)"
    if status_int == 3:
        return True, "status=3 (MERGED)"
    return False, "status={} (unrecognized)".format(status_int)


def _is_case_closed(case):
    """Return True when the case is closed across known SecOps status shapes."""
    return _case_closed_detail(case)[0]


def _case_has_tag(case, tag):
    """Return True when the case has the tag, or when tags are unavailable.

    Candidates are already collected via a tag filter. CaseFullDetails sometimes
    returns an empty tags list even when the case is tagged, so an empty/missing
    tags payload must not reject the case.
    """
    wanted = str(tag).strip().lower()
    if not isinstance(case, dict):
        return False
    if "tags" not in case and "Tags" not in case:
        return True
    tags = _case_field(case, "tags", "Tags", default=[]) or []
    if not isinstance(tags, list):
        tags = [tags]
    if not tags:
        return True
    for item in tags:
        if isinstance(item, dict):
            name = (
                item.get("name")
                or item.get("Name")
                or item.get("tag")
                or item.get("Tag")
                or item.get("value")
                or ""
            )
        else:
            name = item
        if str(name).strip().lower() == wanted:
            return True
    return False


def _skip_reason(case, case_id, case_tag):
    if not case:
        return "case {} could not be loaded".format(case_id)
    if not _case_has_tag(case, case_tag):
        tags = _case_field(case, "tags", "Tags", default=[]) or []
        return "case {} missing tag '{}' (case tags={!r})".format(
            case_id, case_tag, tags
        )
    closed, closed_detail = _case_closed_detail(case)
    if not closed:
        return "case {} is not closed ({})".format(case_id, closed_detail)
    return None


def _case_title(case, case_id):
    return _case_field(
        case,
        "title",
        "displayName",
        "name",
        "description",
        default="Google SecOps Case {}".format(case_id),
    )


def _is_jsm_closed(alert):
    status = str((alert or {}).get("status") or "").strip().lower()
    return status in ("closed", "close", "resolved")


def _resolve_jsm_alert(manager, siemplify, case_id, case_state):
    stored_id = case_state.get("alert_id")
    if stored_id:
        try:
            return manager.get_alert(stored_id)
        except Exception as e:
            siemplify.LOGGER.info(
                "Stored JSM alert {} for case {} is unavailable: {}".format(
                    stored_id, case_id, e
                )
            )

    for alias in (_alias_for_case(case_id), str(case_id)):
        try:
            alert = manager.find_alert_by_alias(alias)
        except Exception as e:
            siemplify.LOGGER.info(
                "Alias lookup {} for case {} failed: {}".format(alias, case_id, e)
            )
            alert = None
        if alert and alert.get("id"):
            case_state["alert_id"] = alert.get("id")
            return alert
    return None


def _first_mapping_value(payload, *names):
    if not isinstance(payload, dict):
        return None
    for name in names:
        value = payload.get(name)
        if value not in (None, ""):
            return value
    return None


def _closure_details(siemplify, case, case_id):
    details = {}
    try:
        payload = siemplify.get_case_closure_details([str(case_id)]) or []
        if isinstance(payload, list) and payload:
            details = payload[0] if isinstance(payload[0], dict) else {}
        elif isinstance(payload, dict):
            details = payload
    except Exception as e:
        siemplify.LOGGER.info(
            "Could not read closure details for case {}: {}".format(case_id, e)
        )

    reason = _first_mapping_value(details, "reason", "Reason") or _case_field(
        case, "reason", "close_reason", "closeReason"
    )
    root_cause = _first_mapping_value(
        details, "root_cause", "rootCause", "RootCause"
    ) or _case_field(case, "root_cause", "rootCause")
    comment = _first_mapping_value(
        details, "comment", "Comment", "closing_comment"
    ) or _case_field(case, "closing_comment", "close_comment")
    return {
        "reason": reason,
        "root_cause": root_cause,
        "comment": comment,
    }


def _close_note(siemplify, case, case_id):
    details = _closure_details(siemplify, case, case_id)
    lines = [
        "Closed from Google SecOps case {}.".format(case_id),
        "Title: {}".format(_case_title(case, case_id)),
    ]
    if details.get("reason"):
        lines.append("Close reason: {}".format(details["reason"]))
    if details.get("root_cause"):
        lines.append("Root cause: {}".format(details["root_cause"]))
    if details.get("comment"):
        lines.append("Close comment: {}".format(details["comment"]))
    return "\n".join(lines)


def _close_open_jsm_alert(manager, siemplify, case, case_id, case_state):
    if case_state.get("jsm_closed"):
        return "already_synced"

    alert = _resolve_jsm_alert(manager, siemplify, case_id, case_state)
    if not alert or not alert.get("id"):
        return "no_jsm_alert"

    alert_id = alert.get("id")
    if _is_jsm_closed(alert):
        case_state["jsm_closed"] = True
        return "already_closed"

    note = _close_note(siemplify, case, case_id)
    try:
        manager.add_alert_note(alert_id, note)
    except Exception as e:
        siemplify.LOGGER.warn(
            "Could not add close note to JSM alert {} for case {}: {}".format(
                alert_id, case_id, e
            )
        )

    manager.close_alert(alert_id, note=note)
    case_state["jsm_closed"] = True
    siemplify.LOGGER.info(
        "Closed JSM Ops alert {} because SecOps case {} is closed.".format(
            alert_id, case_id
        )
    )
    return "closed_jsm"


def main():
    siemplify = SiemplifyJob()
    siemplify.script_name = SCRIPT_NAME

    try:
        config = {}
        try:
            config = siemplify.get_configuration(INTEGRATION_NAME) or {}
        except Exception:
            config = {}

        cloud_id = _config_param(siemplify, config, "JSM Ops Cloud ID")
        api_key = _config_param(siemplify, config, "JSM Ops API Key")
        service_account = _config_param(siemplify, config, "JSM Ops Service Account Email")
        verify_ssl = _to_bool(_config_param(siemplify, config, "Verify SSL", "true"), True)

        case_tag = str(_job_param(siemplify, "Case Tag", "JSM")).strip() or "JSM"
        hours_back = _to_int(_job_param(siemplify, "Hours Backwards", "24"), 24, "Hours Backwards")
        max_cases = _to_int(
            _job_param(siemplify, "Max Cases Per Run", "50"), 50, "Max Cases Per Run"
        )
        environments = _parse_csv(_job_param(siemplify, "Environment", ""))

        manager = JSMOpsManager(
            cloud_id=cloud_id,
            api_key=api_key,
            service_account_email=service_account,
            verify_ssl=verify_ssl,
        )

        case_ids = _collect_closed_case_ids(
            siemplify, case_tag, hours_back, max_cases, environments
        )
        siemplify.LOGGER.info(
            "Found {} candidate closed case(s) for tag '{}'.".format(len(case_ids), case_tag)
        )

        state = _load_state(siemplify)
        processed = 0
        skipped = 0
        closed_jsm = 0
        already_closed = 0
        missing_jsm = 0
        errors = 0

        for case_id in case_ids:
            if processed >= max_cases:
                break
            try:
                case = _get_case(siemplify, case_id)
                reason = _skip_reason(case, case_id, case_tag)
                if reason:
                    skipped += 1
                    siemplify.LOGGER.info("Skipping {}: {}".format(case_id, reason))
                    continue

                processed += 1
                result = _close_open_jsm_alert(
                    manager, siemplify, case, case_id, _case_state(state, case_id)
                )
                if result == "closed_jsm":
                    closed_jsm += 1
                elif result in ("already_closed", "already_synced"):
                    already_closed += 1
                elif result == "no_jsm_alert":
                    missing_jsm += 1
            except Exception as e:
                errors += 1
                siemplify.LOGGER.error("Failed to sync case {}: {}".format(case_id, e))
                siemplify.LOGGER.exception(e)

        _save_state(siemplify, state)
        message = (
            "JSM Ops one-way close sync completed for tag '{}'. "
            "Closed tagged cases processed: {}, JSM alerts closed: {}, "
            "already closed/synced: {}, no linked JSM alert: {}, skipped: {}, errors: {}."
        ).format(
            case_tag, processed, closed_jsm, already_closed, missing_jsm, skipped, errors
        )
        siemplify.LOGGER.info(message)
        if errors:
            raise Exception(message)
        siemplify.end(message, True)
    except Exception as e:
        siemplify.LOGGER.error('Error executing job "{}". Reason: {}'.format(SCRIPT_NAME, e))
        siemplify.LOGGER.exception(e)
        raise


if __name__ == "__main__":
    main()
