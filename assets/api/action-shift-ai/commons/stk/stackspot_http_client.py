import json
import time
import logging
from collections.abc import Callable

import requests
from threading import Lock
from oscli.core.http import get_with_authorization
from oscli.core.http import post_with_authorization
from oscli.core.http import delete_with_authorization
from oscli.core.http import put_with_authorization
from oscli.core.http import patch_with_authorization
from oscli.core.exceptions.http_exception import ForbiddenError


logger = logging.getLogger()


class StackspotHttpClient:
    def __init__(self):
        self.rate_limit = 1
        self.lock = Lock()
        self.last_request_time = 0

    def wait(self):
        logger.info("Waiting for stackspot http client")
        with self.lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
            self.last_request_time = time.time()

    def __make_request(self, method: Callable, url: str, return_json: bool = True, **kw):
        try:
            print(f"Making request to [{method.__name__.upper()}] {url}")
            kw.get("body") and print(f"Request body: \n {json.dumps(kw.get('body'), indent=4)}", url)
            self.wait()
            response = method(url, **{**dict(timeout=120), **kw})
            response.raise_for_status()
            if return_json:
                return response.json() if response.text else None
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"Erro HTTP: {http_err} - Resposta: {http_err.response.text}")
            raise http_err
        except ForbiddenError as e:
            raise Exception(
                f"""
                Stackspot Forbidden Error!
                Response Data:
                - URL: {e.response.url}
                - Response Status Code: {e.response.status_code}
                - Response Headers: {e.response.headers}
                - Response Body(text): {e.response.text}
                """
            ) from e
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Erro de requisição: {req_err}")
            raise req_err
        except ValueError as json_err:
            logger.error(f"Erro ao decodificar JSON: {json_err}")
            raise json_err

    def get(self, **kw):
        return self.__make_request(get_with_authorization, use_cache=False, **kw)

    def post(self, **kw):
        return self.__make_request(post_with_authorization, **kw)

    def delete(self, **kw):
        return self.__make_request(delete_with_authorization, **kw)

    def put(self, **kw):
        return self.__make_request(put_with_authorization, **kw)

    def patch(self, **kw):
        return self.__make_request(patch_with_authorization, **kw)
