from commons.stk.stackspot_http_client import StackspotHttpClient
from oscli import __workflow_base_url__


WORKFLOW_ADD_SUMMARY = "{domain}/v1/executions/{workflow_execution_id}/summary"


class Workflow:
    domain = __workflow_base_url__

    def __init__(self, http_client: StackspotHttpClient, timeout: int = 30):
        self.__http_client = http_client
        self.timeout = timeout

    def add_summary(self, workflow_execution_id: str, title: str, message: str):
        return self.__http_client.put(
            url=WORKFLOW_ADD_SUMMARY.format(domain=self.domain, workflow_execution_id=workflow_execution_id),
            body=dict(
                title=title,
                message=message,
            )
        )