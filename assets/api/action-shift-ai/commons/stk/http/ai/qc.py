import time

from commons.stk.stackspot_http_client import StackspotHttpClient
from oscli import __codebuddy_base_url__


class QuickCommand:
    def __init__(self, http_client: StackspotHttpClient, timeout: int = 30):
        self.__http_client = http_client
        self.timeout = timeout
        self.domain = __codebuddy_base_url__

    def run(self, slug: str, execution_timeout: int = 120, **payload) -> dict:
        exec_id = self.create_execution(slug=slug, **payload)
        return self.wait(exec_id=exec_id, execution_timeout=execution_timeout)

    def wait(self, exec_id: str, execution_timeout: int) -> dict:
        start_time = time.time()
        while True:
            if time.time() - start_time > execution_timeout:
                break

            try:
                response_data = self.get_execution(exec_id)
            except Exception:
                continue

            status = response_data.get('progress', {}).get('status')
            if status == "COMPLETED":
                return response_data.get('result', {})

            elif status == "FAILURE":
                raise RuntimeError(f"Execution failed with status {status}.\n\n Full response: {response_data}")

        raise RuntimeError(f"Execution timed out after {execution_timeout} seconds.")

    def create_execution(self, slug: str, **payload) -> str:
        response = self.__http_client.post(
            url=f"{self.domain}/v1/quick-commands/create-execution/{slug}",
            body=payload,
            timeout=self.timeout
        )
        return response

    def get_execution(self, execution_id: str) -> dict:
        response = self.__http_client.get(
            url=f"{self.domain}/v1/quick-commands/callback/{execution_id}",
            timeout=self.timeout
        )
        return response
