import json

import requests
from requests.auth import HTTPBasicAuth


class JSMOpsManager(object):
    """Wrapper for the Atlassian Jira Service Management Ops Alerts API."""

    def __init__(self, cloud_id, api_key, service_account_email, verify_ssl=True):
        self.cloud_id = cloud_id
        self.api_key = api_key
        self.service_account_email = service_account_email
        self.verify_ssl = verify_ssl
        self.base_url = "https://api.atlassian.com/jsm/ops/api/{}/v1".format(cloud_id)
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(service_account_email, api_key)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path):
        return "{}/{}".format(self.base_url, path.lstrip("/"))

    @staticmethod
    def validate_response(response, expected_status_codes, error_msg="An error occurred"):
        if response.status_code not in expected_status_codes:
            details = response.text
            try:
                details = response.json()
            except Exception:
                pass
            raise Exception(
                "{} Status code: {}. Details: {}".format(
                    error_msg, response.status_code, details
                )
            )
        if not response.text:
            return {}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    def test_connectivity(self):
        """Verify credentials by listing a single alert page."""
        response = self.session.get(
            self._url("alerts"),
            params={"offset": 0, "size": 1},
            verify=self.verify_ssl,
        )
        self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to validate JSM Ops connectivity.",
        )
        return True

    def create_alert(
        self,
        message,
        title,
        priority,
        team_id,
        tags=None,
        alias=None,
        source=None,
        details=None,
    ):
        payload = {
            "message": title,
            "description": message,
            "priority": priority,
            "responders": [{"id": team_id, "type": "team"}],
            "visibleTo": [{"id": team_id, "type": "team"}],
        }
        if tags:
            payload["tags"] = tags
        if alias:
            payload["alias"] = alias
        if source:
            payload["source"] = source
        if details:
            payload["details"] = details

        response = self.session.post(
            self._url("alerts"),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            # JSM Ops may return 202 Accepted or 200 OK for async create.
            expected_status_codes=(200, 202),
            error_msg="Failed to create JSM Ops alert.",
        )

    def get_request_status(self, request_id):
        response = self.session.get(
            self._url("alerts/requests/{}".format(request_id)),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to get JSM Ops request status.",
        )

    def get_alert(self, alert_id):
        response = self.session.get(
            self._url("alerts/{}".format(alert_id)),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to get JSM Ops alert.",
        )

    def get_alert_by_alias(self, alias):
        response = self.session.get(
            self._url("alerts/alias"),
            params={"alias": alias},
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to get JSM Ops alert by alias.",
        )

    def find_alert_by_alias(self, alias):
        """Return an alert for alias, including closed alerts when the alias API misses them."""
        try:
            alert = self.get_alert_by_alias(alias)
            if alert:
                return alert
        except Exception:
            pass

        safe_alias = str(alias).replace('"', "")
        result = self.list_alerts(
            query='alias:"{}"'.format(safe_alias),
            size=5,
            offset=0,
        )
        values = result.get("values") or result.get("data") or []
        if not values:
            return None
        alert = values[0]
        alert_id = alert.get("id")
        if alert_id:
            try:
                return self.get_alert(alert_id)
            except Exception:
                return alert
        return alert

    def list_alerts(self, query=None, size=None, offset=None, sort=None, order=None):
        params = {}
        if query:
            params["query"] = query
        if size is not None:
            params["size"] = size
        if offset is not None:
            params["offset"] = offset
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order

        response = self.session.get(
            self._url("alerts"),
            params=params or None,
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to list JSM Ops alerts.",
        )

    def iter_alerts(self, query=None, page_size=50, max_alerts=50, sort="updatedAt", order="desc"):
        """Return up to max_alerts from paginated list-alerts results."""
        collected = []
        offset = 0
        page_size = max(1, min(int(page_size), 100))
        max_alerts = max(1, int(max_alerts))
        while len(collected) < max_alerts:
            size = min(page_size, max_alerts - len(collected))
            payload = self.list_alerts(
                query=query,
                size=size,
                offset=offset,
                sort=sort,
                order=order,
            )
            values = payload.get("values") or payload.get("data") or []
            if not isinstance(values, list) or not values:
                break
            collected.extend(values)
            if len(values) < size:
                break
            offset += len(values)
        return collected[:max_alerts]

    def list_alert_logs(self, alert_id, after=None, size=None):
        params = {}
        if after:
            params["after"] = after
        if size is not None:
            params["size"] = size
        response = self.session.get(
            self._url("alerts/{}/logs".format(alert_id)),
            params=params or None,
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to list JSM Ops alert logs.",
        )

    def list_all_alert_logs(self, alert_id, page_size=50, max_pages=10):
        logs = []
        after = None
        for _ in range(max_pages):
            payload = self.list_alert_logs(alert_id, after=after, size=page_size)
            values = payload.get("values") or payload.get("data") or []
            if not isinstance(values, list) or not values:
                break
            logs.extend(values)
            next_link = (payload.get("links") or {}).get("next") or ""
            if not next_link:
                break
            after = values[-1].get("id") or values[-1].get("logTime")
            if not after:
                break
        return logs

    def close_alert(self, alert_id, note=None):
        payload = {}
        if note:
            payload["note"] = note
        response = self.session.post(
            self._url("alerts/{}/close".format(alert_id)),
            data=json.dumps(payload) if payload else None,
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to close JSM Ops alert.",
        )

    def acknowledge_alert(self, alert_id):
        response = self.session.post(
            self._url("alerts/{}/acknowledge".format(alert_id)),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to acknowledge JSM Ops alert.",
        )

    def escalate_alert(self, alert_id, escalation_id):
        payload = {"escalationId": escalation_id}
        response = self.session.post(
            self._url("alerts/{}/escalate".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to escalate JSM Ops alert.",
        )

    def assign_alert(self, alert_id, account_id):
        payload = {"accountId": account_id}
        response = self.session.post(
            self._url("alerts/{}/assign".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to assign JSM Ops alert.",
        )

    def add_responder(self, alert_id, responder_id, responder_type):
        payload = {"id": responder_id, "type": responder_type}
        response = self.session.post(
            self._url("alerts/{}/responders".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to add responder to JSM Ops alert.",
        )

    def add_alert_note(self, alert_id, note):
        payload = {"note": note}
        response = self.session.post(
            self._url("alerts/{}/notes".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to add note to JSM Ops alert.",
        )

    def list_alert_notes(self, alert_id, after=None, size=None):
        params = {}
        if after:
            params["after"] = after
        if size is not None:
            params["size"] = size
        response = self.session.get(
            self._url("alerts/{}/notes".format(alert_id)),
            params=params or None,
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to list JSM Ops alert notes.",
        )

    def list_all_alert_notes(self, alert_id, page_size=50, max_pages=20):
        notes = []
        after = None
        for _ in range(max_pages):
            payload = self.list_alert_notes(alert_id, after=after, size=page_size)
            values = payload.get("values") or payload.get("data") or []
            if not isinstance(values, list) or not values:
                break
            notes.extend(values)
            next_link = (payload.get("links") or {}).get("next") or ""
            if not next_link:
                break
            after = values[-1].get("id")
            if not after:
                break
        return notes

    def update_priority(self, alert_id, priority):
        payload = {"priority": priority}
        response = self.session.patch(
            self._url("alerts/{}/priority".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to update JSM Ops alert priority.",
        )

    def add_tags(self, alert_id, tags):
        payload = {"tags": tags}
        response = self.session.post(
            self._url("alerts/{}/tags".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to add tags to JSM Ops alert.",
        )

    def add_extra_properties(self, alert_id, properties):
        payload = {"extraProperties": properties}
        response = self.session.post(
            self._url("alerts/{}/extra-properties".format(alert_id)),
            data=json.dumps(payload),
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(202,),
            error_msg="Failed to add extra properties to JSM Ops alert.",
        )

    def get_on_calls(self, schedule_id, date=None):
        params = {}
        if date:
            params["date"] = date
        response = self.session.get(
            self._url("schedules/{}/on-calls".format(schedule_id)),
            params=params or None,
            verify=self.verify_ssl,
        )
        return self.validate_response(
            response,
            expected_status_codes=(200,),
            error_msg="Failed to get JSM Ops on-call responders.",
        )
