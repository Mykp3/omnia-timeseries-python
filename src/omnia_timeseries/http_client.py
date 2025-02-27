from typing import Literal, Optional, TypedDict, Union, Dict, Any
from azure.identity import ManagedIdentityCredential
import requests
import logging
logging.basicConfig(level=logging.DEBUG)
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
    def __init__(self, resource_id: str):
        self._resource_id = resource_id

    def _get_access_token(self) -> str:
        auth_endpoint = (
            "https://management.azure.com/.default"
            if "ml" in self._resource_id.lower()
            else f"{self._resource_id}/.default"
        )

        try:
            # F R E S H  C R E D E N T I A L  PER CALLL
            azure_credential = ManagedIdentityCredential()
            token = azure_credential.get_token(auth_endpoint).token
            print(f"Successfully retrieved token: {token[:10]}...")
            return token

        except Exception as e:
            print(f"Error fetching token: {e}")
            raise

    def request(
        self,
        request_type: RequestType,
        url: str,
        accept: ContentType = "application/json",
        payload: Optional[Union[TypedDict, dict, list]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        access_token = self._get_access_token()
    
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': accept,
            'User-Agent': f'Omnia Timeseries SDK/{version} {system_version_string}'
        }
        return _request(
            request_type=request_type,
            url=url,
            headers=headers,
            payload=payload,
            params=params
        )