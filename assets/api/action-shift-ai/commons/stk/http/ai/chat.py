import json

from commons.stk.stackspot_http_client import StackspotHttpClient
from oscli import __codebuddy_base_url__


class CodeBuddy:
    def __init__(self, http_client: StackspotHttpClient, timeout: int = 30):
        self.__http_client = http_client
        self.timeout = timeout
        self.domain = __codebuddy_base_url__

    def chat(self, prompt: str) -> str:
        result = self.__http_client.post(
            url=f"{self.domain}/v3/chat",
            body={
                "context": {
                    "upload_ids": [],
                    "agent_built_in": True,
                },
                "user_prompt": prompt
            },
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=(5.0, 180.0)
        )

        response = []
        completed = False

        for raw_line in result.iter_lines():
            if not raw_line:
                continue

            line = raw_line.decode("utf-8").strip()

            if line.startswith("data:"):
                try:
                    data_content = json.loads(line[5:].strip())
                    if "answer" in data_content and isinstance(data_content["answer"], str):
                        response.append(data_content["answer"])
                except json.JSONDecodeError:
                    continue
            elif line.startswith("event: end_event"):
                completed = True
                break

        if not completed:
            raise Exception("Stream truncado: A conexão foi fechada antes do 'end_event' ser recebido.")

        return str().join(response).strip()

