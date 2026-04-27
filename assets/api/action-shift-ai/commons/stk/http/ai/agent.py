import json
from typing import Optional, List

from commons.stk.stackspot_http_client import StackspotHttpClient
from oscli import __cli_command__


domain = {
    "stk": "https://genai-inference-app.stackspot.com",
    "stk-stg": "https://genai-inference-app.stg.stackspot.com",
    "local": "https://agent.com"
}
agent_tools_domain = {
    "stk": "https://genai-agent-tools-api.stackspot.com",
    "stk-stg": "https://genai-agent-tools-api.stg.stackspot.com",
    "local": "https://agent-tools.com"
}
AGENT_CHAT = "{domain}/v1/agent/{agent_id}/chat"
LIST_AGENT = "{domain}/v3/agents"
CREATE_AGENT = "{domain}/v1/agents"
DELETE_AGENT = "{domain}/v1/agents/{agent_id}"

class Agent:
    domain = domain[__cli_command__]
    agent_tools_domain = agent_tools_domain[__cli_command__]

    def __init__(self, http_client: StackspotHttpClient, timeout: int = 300):
        self.__http_client = http_client
        self.timeout = timeout

    def chat(
        self,
        agent_id: str,
        prompt: str,
        conversation_id: str = str(),
        deep_search_ks: bool = True,
        streaming: bool = False,
        stackspot_knowledge: bool = False,
        return_ks_in_response: bool = False,
    ) -> str:
        print(f"Chatting with agent id: {agent_id}")
        payload = {
            "conversation_id": conversation_id,
            "deep_search_ks": deep_search_ks,
            "streaming": True,
            "user_prompt": prompt,
            "stackspot_knowledge": stackspot_knowledge,
            "return_ks_in_response": return_ks_in_response
        }

        response = self.__http_client.post(
            url=AGENT_CHAT.format(domain=self.domain, agent_id=agent_id),
            body=payload,
            timeout=60,
            stream=True,
            return_json=False,
        )

        answers = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("data: "):
                data_json = line[len("data: "):]
                try:
                    data = json.loads(data_json)
                    answers.append(data.get("message", ""))
                except json.JSONDecodeError:
                    pass

        response = "".join(answers)
        print(f"Chatting with agent id: {agent_id} - {response}")
        return response


    def list_agents(self, **params) -> dict:
        print("Listing agents...")
        return self.__http_client.get(
            url=LIST_AGENT.format(domain=self.agent_tools_domain),
            params=params,
            timeout=self.timeout
        )

    def delete(self, agent_id: str) -> dict:
        print(f"Deleting agent {agent_id} ")
        return self.__http_client.delete(
            url=DELETE_AGENT.format(domain=self.agent_tools_domain, agent_id=agent_id),
            timeout=self.timeout
        )

    def create(
        self,
        slug: str,
        name: str,
        system_prompt: str,
        type: str = "CONVERSATIONAL",
        enabled_tools: bool = True,
        detail_mode: bool = True,
        avatar: str = str(),
        ks_ids: Optional[List[str]] = None,
        max_number_of_kos: int = 20,
        relevancy_threshold: int = 40,
        enabled_structured_outputs: bool = True,
    ) -> dict:
        print(f"Creating agent {slug}")
        return self.__http_client.post(
            url=CREATE_AGENT.format(domain=self.agent_tools_domain),
            body={
                "type": type,
                "name": name,
                "system_prompt": system_prompt,
                "avatar": avatar,
                "structured_output": None,
                "enabled_structured_outputs": enabled_structured_outputs,
                "suggested_prompts": [],
                "slug": slug,
                "knowledge_sources_config": {
                    "knowledge_sources": ks_ids,
                    "max_number_of_kos": max_number_of_kos,
                    "relevancy_threshold": relevancy_threshold
                },
                "tools": [],
                "builtin_tools_ids": [],
                "custom_tools": [],
                "enabled_tools": enabled_tools,
                "detail_mode": detail_mode
            },
            timeout=self.timeout
        )