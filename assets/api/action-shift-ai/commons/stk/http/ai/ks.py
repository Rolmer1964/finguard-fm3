import time

from typing import Optional
from logging import getLogger

from commons.stk.stackspot_http_client import StackspotHttpClient
from libs.macosx_11_0_arm64 import requests
from oscli import __cli_command__
from oscli.core.auth import get_account_id_v2, get_email

logger = getLogger()

domain = {
    "stk": "https://data-integration-api.stackspot.com",
    "stk-stg": "https://genai-data-integration-api.stg.stackspot.com",
    "local": "https://ks.com"
}
GET_BY_SLUG = "{domain}/v1/knowledge-sources/{ks_slug}"
GET_ALL_KS = "{domain}/v1/knowledge-sources"
CREATE_KS = "{domain}/v1/knowledge-sources"
UPDATE_KS = "{domain}/v1/knowledge-sources/{ks_slug}"
GET_UPLOAD_URL = "{domain}/v2/file-upload/form"
SPLIT_UPLOAD_FILE = "{domain}/v1/file-upload/{upload_id}/split"
INDEX_UPLOAD_FILE = "{domain}/v1/file-upload/{upload_id}"
CHECK_UPLOAD_FILE = "{domain}/v1/file-upload/{upload_id}"
DELETE_KS = "{domain}/v1/knowledge-sources/{ks_slug}"


class KnowledgeSource:
    domain = domain[__cli_command__]

    def __init__(self, http_client: StackspotHttpClient, timeout: int = 30):
        self.__http_client = http_client
        self.timeout = timeout

    @property
    def headers(self):
        return {"accept": "application/json", "content-type": "application/json"}

    def delete(self, ks_slug: str):
        print(f"Deleting KS: {ks_slug}")
        return self.__http_client.delete(
            url=DELETE_KS.format(domain=self.domain, ks_slug=ks_slug),
            headers={"x-account-id": get_account_id_v2(), "x-username": get_email() , **self.headers},
            timeout=self.timeout
        )

    def list(self, visibility: Optional[str] = None):
        print(f"Listing KS: {visibility}")
        params = dict()
        if visibility:
            params["visibility"] = visibility

        return self.__http_client.get(
            url=f"{self.domain}/v1/knowledge-sources",
            params=params,
            headers=self.headers,
            timeout=self.timeout
        )

    def get_by_slug(self, ks_slug: str) -> dict:
        print(f"Getting KS: {ks_slug}")
        return self.__http_client.get(
            url=GET_BY_SLUG.format(domain=self.domain, ks_slug=ks_slug),
            headers=self.headers,
            timeout=self.timeout
        )

    def get_all_ks(self, visibility: str = 'personal') -> dict:
        print(f"Getting ALL KS")
        params = {
            "visibility": visibility,
            "order": "a-to-z"
        }
        return self.__http_client.get(
            url=GET_ALL_KS.format(domain=self.domain),
            params=params,
            headers=self.headers,
            timeout=self.timeout
        )

    def create(
        self,
        name: str,
        slug: str,
        description: str,
        visibility_level: str = "personal",
        ks_type: str = "custom",
        default: bool = False,
        creator: str = "",
        **kwargs
    ) -> dict:
        print(f"Creating KS: {slug}")
        ks_response = self.__http_client.post(
            url=CREATE_KS.format(domain=self.domain),
            body={
                "name": name,
                "slug": slug,
                "description": description,
                "default": default,
                "visibility_level": visibility_level,
                "creator": creator,
                "type": ks_type,
                **kwargs,
            },
            headers=self.headers,
            timeout=self.timeout
        )
        logger.info('Sleeping 10 seconds due async permissions at Knowledge Source creation...')
        time.sleep(10) # DONT REMOVE THIS SLEEP. ITS USED FOR ASYNC PERMISSIONS AT KS CREATION
        return ks_response


    def patch(self, ks_slug: str, **kw) -> dict:
        print(f"Patching KS: {ks_slug}")
        return self.__http_client.patch(
            url=UPDATE_KS.format(domain=self.domain, ks_slug=ks_slug),
            headers=self.headers,
            body=kw,
            timeout=self.timeout
        )

    def get_upload_url(self, file_name, target_id, target_type, expiration):
        print(f"Getting Upload URL: {file_name}")
        url = GET_UPLOAD_URL.format(domain=self.domain, ks_slug=file_name)
        payload = {
            "file_name": file_name,
            "target_id": target_id,
            "target_type": target_type,
            "expiration": expiration
        }
        return self.__http_client.post(
            url=url,
            body=payload, 
            headers={'Content-Type':'application/json'}
        )

    def upload_file(self, upload_url, file_path, form_data):
        print(f"Uploading file: {file_path}")
        with open(file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(upload_url, data=form_data, files=files)
            print(f"Uploading file response: {response}")
            response.raise_for_status()
            return response.json() if response.content else None

    def split_upload_file(self, upload_id):
        print(f"Splitting file: {upload_id}")
        url = SPLIT_UPLOAD_FILE.format(domain=self.domain, upload_id=upload_id)
        return self.__http_client.post(
            url=url,
            body={
                "split_overlap": 0,
                "split_quantity": None,
                "split_strategy": "NONE"
            }
        )

    def index_upload_file(self, upload_id):
        print(f"Indexing file: {upload_id}")
        url = INDEX_UPLOAD_FILE.format(domain=self.domain, upload_id=upload_id)
        payload = {
            "split_strategy": "NONE",
            "split_quantity": None,
            "split_overlap": 0
        }
        return self.__http_client.post(
            url=url,
            body=payload, 
            headers={'Content-Type':'application/json'}
        )

    def check_upload_status(self, upload_id):
        print(f"Checking status of file: {upload_id}")
        url = CHECK_UPLOAD_FILE.format(domain=self.domain, upload_id=upload_id)
        return self.__http_client.get(url=url)
