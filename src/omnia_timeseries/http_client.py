from typing import Literal, Optional, TypedDict, Union, Dict, Any
from azure.identity import ManagedIdentityCredential
import requests
import logging

from omnia_timeseries.helpers import retry
from omnia_timeseries.models import TimeseriesRequestFailedException
from importlib import metadata
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import platform
import os

ContentType = Literal["application/json",
                      "application/protobuf", "application/x-google-protobuf"]

RequestType = Literal['get', 'put', 'post', 'patch', 'delete']

logger = logging.getLogger(__name__)
version = metadata.version("omnia_timeseries")
system_version_string = f'({platform.system()}; Python {platform.version()})' if platform.system(
) else f'(Python {platform.version()})'

RequestsInstrumentor().instrument()

@retry(logger=logger)
def _request(
    request_type: RequestType,
    url: str,
    headers: Dict[str, Any],
    payload: Optional[Union[TypedDict, dict, list]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], bytes]:

    response = requests.request(
        request_type, url, headers=headers, json=payload, params=params)
    if not response.ok:
        raise TimeseriesRequestFailedException(response)
    if not "Accept" in headers or headers["Accept"] == "application/json":
        return response.json()
    else:
        return response.content


class HttpClient:
    def __init__(self, azure_credential: ManagedIdentityCredential, resource_id: str, base_url: str):
        self._azure_credential = azure_credential
        self._resource_id = resource_id
        self._base_url = base_url

    def _sanitize_for_mgmt(self):
        """
        If 'ml' is found in the URL, substitute both resource_id and base_url
        with management endpoint.
        """
        if "ml" in self._base_url.lower() or "ml" in self._resource_id.lower():
            print("Substituting with management.azure.com endpoint due to 'ml' in URL.")
            self._base_url = "https://management.azure.com"
            self._resource_id = "https://management.azure.com/.default"
        else:
            self._resource_id = f"{self._resource_id}/.default"

    def _get_access_token(self) -> str:
        try:
            self._sanitize_for_mgmt()

            print(f"Requesting token from: {self._resource_id}")
            token = self._azure_credential.get_token(self._resource_id).token
            print(f"Successfully retrieved token: {token[:10]}...")
            return token

        except Exception as e:
            print(f" Error fetching token: {e}")
            raise

    def request(
        self,
        request_type: RequestType,
        url: str,
        accept: ContentType = "application/json",
        payload: Optional[Union[TypedDict, dict, list]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:

        access_token = self._azure_credential.get_token(
            f'{self._resource_id}/.default')  # handles caching and refreshing internally
        headers = {
            'Authorization': f'Bearer {access_token.token}',
            'Content-Type': 'application/json',
            'Accept': accept,
            'User-Agent': f'Omnia Timeseries SDK/{version} {system_version_string}'
        }
        return _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)