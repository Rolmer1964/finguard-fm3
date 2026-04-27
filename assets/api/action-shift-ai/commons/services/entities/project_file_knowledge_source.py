import logging
from commons.services.ai import AiServices
from commons.services.file import FileServices
from commons.stk.stackspot_http_client import StackspotHttpClient

logger = logging.getLogger(__name__)


class ProjectFileKnowledgeSource:
    def __init__(
        self,
        slug: str,
        description: str,
        directory: str,
        ai_services: AiServices = None,
        delete_ks: bool = False,
    ):
        formatted_slug = slug.lower()[:80].replace("admin","a") 
        self.slug = formatted_slug
        self.name = formatted_slug
        self.description = description
        self.directory = directory
        self.ai_services = ai_services or AiServices(stackspot_http_client=StackspotHttpClient())
        self.ks_id = None
        self.delete_ks = delete_ks

    def __enter__(self):
        self.ks_id = self.ai_services.create_knowledge_source(
            ks_slug=self.slug,
            name=self.name,
            type="project_file",
            description=self.description,
            on_conflict_delete=True
        )
        self.upload_project_files()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.delete_ks and self.ai_services.delete_knowledge_source(ks_slug=self.slug)
        except Exception as ex:
            logger.error("Failed to delete knowledge source")
            logger.exception(ex)

    def upload_project_files(self):
        zip_file = FileServices.gen_zip_from_dir(directory=self.directory, max_size=5000)
        self.ai_services.multi_upload_knowledge_source(ks_slug=self.slug, zip_file=zip_file)
