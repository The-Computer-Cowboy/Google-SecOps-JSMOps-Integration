from SiemplifyAction import SiemplifyAction
from SiemplifyUtils import output_handler
from ScriptResult import EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED
from JSMOpsManager import JSMOpsManager


INTEGRATION_NAME = "JSM Ops"
SCRIPT_NAME = "List Alerts"


def _get_bool_param(siemplify, param_name, default=True):
    value = siemplify.extract_configuration_param(
        provider_name=INTEGRATION_NAME,
        param_name=param_name,
        default_value=str(default),
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _parse_int_param(value, default, param_name):
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        raise Exception("{} must be an integer. Received: {}".format(param_name, value))


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

        query = siemplify.extract_action_param(
            param_name="Query", print_value=True, default_value=""
        )
        size_raw = siemplify.extract_action_param(
            param_name="Size", print_value=True, default_value="20"
        )
        offset_raw = siemplify.extract_action_param(
            param_name="Offset", print_value=True, default_value="0"
        )
        size = _parse_int_param(size_raw, 20, "Size")
        offset = _parse_int_param(offset_raw, 0, "Offset")

        manager = JSMOpsManager(
            cloud_id=cloud_id,
            api_key=api_key,
            service_account_email=service_account,
            verify_ssl=verify_ssl,
        )
        json_results = manager.list_alerts(
            query=query if query else None,
            size=size,
            offset=offset,
        )
        siemplify.result.add_result_json(json_results)
        values = json_results.get("values") or json_results.get("data") or []
        count = len(values) if isinstance(values, list) else "N/A"
        output_message = "Successfully listed JSM Ops alerts. Returned: {}.".format(count)
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
