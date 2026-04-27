import logging
from typing import Dict, Any, Optional

from commons.services.ai import AiServices
from commons.stk.stackspot_http_client import StackspotHttpClient

logger = logging.getLogger(__name__)


def _is_rqc_access_error(error_message: str) -> bool:
    message = (error_message or "").lower()
    return (
            "forbidden" in message
            or "403" in message
            or "create-execution" in message
    )


class QuickCommand:
    def __init__(
            self,
            slug: str,
            execution_timeout: int = 300,
            ai_services: Optional[AiServices] = None,
            validate_response: bool = True
    ):
        self.slug = slug
        self.execution_timeout = execution_timeout
        self.ai_services = ai_services or AiServices(
            stackspot_http_client=StackspotHttpClient()
        )
        self.validate_response = validate_response
        self.execution_id: Optional[str] = None
        self.result: Optional[Dict] = None

    def __enter__(self):
        logger.info(f"🚀 Iniciando Quick Command: {self.slug}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"❌ Erro durante execução do QC {self.slug}: {exc_val}")
        else:
            logger.info(f"✅ Quick Command {self.slug} concluído com sucesso")

        return False

    def execute(self, **inputs) -> Dict[str, Any]:
        logger.info(f"📤 Executando QC {self.slug}")
        logger.info(f"📋 Inputs recebidos: {inputs}")

        try:
            self.result = self.ai_services._qc.run(
                slug=self.slug,
                execution_timeout=self.execution_timeout,
                **inputs
            )

            logger.info(f"✅ QC executado com sucesso")
            logger.info(f"📄 Resultado: {self.result}")

            if self.validate_response:
                self._validate_execution_plan_response(self.result)

            return self.result

        except RuntimeError as e:
            logger.error(f"❌ Erro ao executar QC {self.slug}: {e}")
            if _is_rqc_access_error(str(e)):
                raise RuntimeError(
                    f"Não foi possível executar o RQC '{self.slug}' por falta de acesso. "
                    f"Compartilhe esse RQC com a conta utilizada no módulo para que ele tenha permissão de execução. "
                    f"Consulte a documentação na página do módulo."
                ) from e
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao executar QC {self.slug}: {e}")
            if _is_rqc_access_error(str(e)):
                raise RuntimeError(
                    f"Não foi possível executar o RQC '{self.slug}' por falta de acesso. "
                    f"Compartilhe esse RQC com a conta utilizada no módulo para que ele tenha permissão de execução. "
                    f"Consulte a documentação na página do módulo."
                ) from e
            raise RuntimeError(f"Falha na execução do QC: {e}") from e

    def get_execution_id(self) -> Optional[str]:
        return self.execution_id

    def get_result(self) -> Optional[Dict]:
        return self.result
