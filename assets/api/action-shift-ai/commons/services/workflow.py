import os

from commons.stk.http.edp.workflow import Workflow
from commons.stk.stackspot_http_client import StackspotHttpClient


class WorkflowServices:
    def __init__(self, stackspot_http_client: StackspotHttpClient):
        self.stackspot_http_client = stackspot_http_client
        self._workflow = Workflow(self.stackspot_http_client)

    def add_summary(self, title: str, message: str):
        exec_id = os.getenv("STK_EXECUTION_ID")
        self._workflow.add_summary(workflow_execution_id=exec_id, title=title, message=message)