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
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
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
    def __init__(self, azure_credential: ManagedIdentityCredential, resource_id: str):
        self._azure_credential = azure_credential
        self._resource_id = resource_id
    def request(
        self,
        request_type: str,
        url: str,
        accept: str = "application/json",
        payload: Optional[Union[dict, list]] = None,
        params: Optional[dict] = None
    ) -> Any:

        if "ml" in self._resource_id.lower():
            auth_endpoint = "https://management.azure.com/.default"
        else:
            auth_endpoint = f"{self._resource_id}/.default"

        azure_credential = ManagedIdentityCredential(client_id=CLIENT_ID)
        access_token = azure_credential.get_token(auth_endpoint)

        headers = {
            'Authorization': f'Bearer {access_token.token}',
            'Content-Type': 'application/json',
            'Accept': accept,
            'User-Agent': f'Omnia Timeseries SDK/{version} {system_version_string}'
        }
        return _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)