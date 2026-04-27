import logging

from commons.services.ai import AiServices
from commons.services.entities.agent import Agent

logger = logging.getLogger(__name__)
EXTERNAL_PLACEHOLDER_SLUG = "shift-ai-external-agent-slug"
EXTERNAL_PLACEHOLDER_SYSTEM_PROMPT = "shift-ai-external-agent-system-prompt"


def _is_external_agent_access_error(error_message: str) -> bool:
    message = (error_message or "").lower()
    return "forbidden" in message or "403" in message


class ExternalAgent(Agent):
    def __init__(
            self,
            agent_id: str,
            conversation_id: str = None,
            ai_services: AiServices = None,
    ):
        super().__init__(
            slug=EXTERNAL_PLACEHOLDER_SLUG,
            system_prompt=EXTERNAL_PLACEHOLDER_SYSTEM_PROMPT,
            conversation_id=conversation_id,
            ai_services=ai_services,
            delete_agent=False,
            ks_ids=[],
        )
        self.agent_id = agent_id

    def __enter__(self):
        logger.info(f"Using existing agent_id={self.agent_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Skipping agent deletion")
        return

    def chat(self, prompt: str, **kwargs):
        try:
            return super().chat(prompt=prompt, **kwargs)
        except Exception as e:
            if _is_external_agent_access_error(str(e)):
                raise RuntimeError(
                    f"Não foi possível usar o agente externo '{self.agent_id}' por falta de acesso. "
                    f"Compartilhe esse agente com a conta utilizada no módulo para que ele tenha permissão de uso. "
                    f"Consulte a documentação na página do módulo."
                ) from e
            raise
