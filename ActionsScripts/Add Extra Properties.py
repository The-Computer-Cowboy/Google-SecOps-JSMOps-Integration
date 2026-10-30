import json

from SiemplifyAction import SiemplifyAction
from SiemplifyUtils import output_handler
from ScriptResult import EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED
from JSMOpsManager import JSMOpsManager


INTEGRATION_NAME = "JSM Ops"
SCRIPT_NAME = "Add Extra Properties"


def _get_bool_param(siemplify, param_name, default=True):
    value = siemplify.extract_configuration_param(
        provider_name=INTEGRATION_NAME,
        param_name=param_name,
        default_value=str(default),
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _parse_extra_properties(raw_properties):
    try:
        properties = json.loads(raw_properties)
    except Exception:
        raise Exception(
            "Extra Properties must be a valid JSON object string. Received: {}".format(
                raw_properties
            )
        )
    if not isinstance(properties, dict):
        raise Exception("Extra Properties must be a JSON object (key/value map).")
    return properties


@output_handler
def main():
    siemplify = SiemplifyAction()
    siemplify.script_name = SCRIPT_NAME
    status = EXECUTION_STATE_COMPLETED
    result_value = True
    output_message = ""
    json_results = {}

    try:
        cloud_id = siemplify.extract_configuration_param(
            provider_name=INTEGRATION_NAME, param_name="JSM Ops Cloud ID"
        )
        api_key = siemplify.extract_configuration_param(
            provider_name=INTEGRATION_NAME, param_name="JSM Ops API Key"
        )
        service_account = siemplify.extract_configuration_param(
            provider_name=INTEGRATION_NAME, param_name="JSM Ops Service Account Email"
        )
        verify_ssl = _get_bool_param(siemplify, "Verify SSL", default=True)

        alert_id = siemplify.extract_action_param(param_name="Alert ID", print_value=True)
        properties_raw = siemplify.extract_action_param(
            param_name="Extra Properties", print_value=False
        )
        properties = _parse_extra_properties(properties_raw)

        manager = JSMOpsManager(
            cloud_id=cloud_id,
            api_key=api_key,
            service_account_email=service_account,
            verify_ssl=verify_ssl,
        )
        json_results = manager.add_extra_properties(alert_id, properties)
        siemplify.result.add_result_json(json_results)
        output_message = (
            "Successfully submitted add-extra-properties request for JSM Ops alert {}.".format(
                alert_id
            )
        )
        siemplify.LOGGER.info(output_message)
    except Exception as e:
        siemplify.LOGGER.error('Error executing action "{}". Reason: {}'.format(SCRIPT_NAME, e))
        siemplify.LOGGER.exception(e)
        status = EXECUTION_STATE_FAILED
        result_value = False
        output_message = 'Error executing action "{}". Reason: {}'.format(SCRIPT_NAME, e)

    siemplify.end(output_message, result_value, status)


if __name__ == "__main__":
    main()
