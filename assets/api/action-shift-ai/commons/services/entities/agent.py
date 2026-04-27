import uuid
import logging
import time
from typing import Optional, List

from commons.services.ai import AiServices
from commons.stk.stackspot_http_client import StackspotHttpClient


logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self,
        slug: str,
        system_prompt: str,
        on_conflict_delete: bool = True,
        conversation_id: str = None,
        ai_services: AiServices = None,
        delete_agent: bool = True,
        ks_ids: Optional[List[str]] = None,
    ):
        formatted_slug = slug.lower()[:80].replace("admin","a")
        self.slug = formatted_slug
        self.name = formatted_slug
        self.system_prompt = system_prompt
        self.agent_id = None
        self.ks_ids = ks_ids or []
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.on_conflict_delete = on_conflict_delete
        self.ai_services = ai_services or AiServices(stackspot_http_client=StackspotHttpClient())
        self.delete_agent = delete_agent

    def __enter__(self):
        self.agent_id = self.ai_services.create_agent(
            name=self.name,
            slug=self.slug,
            system_prompt=self.system_prompt,
            on_conflict_delete=self.on_conflict_delete,
            ks_ids=self.ks_ids,
        )
        logger.info('Sleeping 10 seconds due async permissions at agent creation...')
        time.sleep(10) # DONT REMOVE THIS SLEEP. ITS USED FOR ASYNC PERMISSIONS AT AGENT CREATION
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.delete_agent and self.ai_services.delete_agent(agent_id=self.agent_id)
        except Exception as ex:
            logger.error("Failed to delete agent")
            logger.exception(ex)

    def chat(self, prompt: str, **kwargs):
        return self.ai_services.call_agent(
            agent_id=self.agent_id,
            prompt=prompt,
            conversation_id=self.conversation_id,
            **{
                **dict(
                    deep_search_ks=True,
                    streaming=False,
                    stackspot_knowledge=False,
                    return_ks_in_response=False
                ),
                **kwargs,
            }
        )