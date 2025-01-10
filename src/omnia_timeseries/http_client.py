from typing import Literal, Optional, TypedDict, Union, Dict, Any
from azure.identity._internal.msal_credentials import MsalCredential
import requests
import logging
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import os


from omnia_timeseries.helpers import retry
from omnia_timeseries.models import TimeseriesRequestFailedException
from importlib import metadata
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import platform

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
    def __init__(self, client_id: str, resource_id: str):
        self._resource_id = resource_id
        self._access_token = self._get_access_token(client_id)

    def _get_access_token(self, client_id: str) -> str:
        try:
            if client_id:
                # AKS SETUP
                print(f"Using ManagedIdentityCredential with client_id: {client_id}")
                azure_credential = ManagedIdentityCredential(client_id=client_id)
            else:
                # CLOUD SHELL SETIP
                print("Using DefaultAzureCredential")
                azure_credential = DefaultAzureCredential()

            token = azure_credential.get_token(self.get_auth_endpoint(self._resource_id)).token
            return token

        except Exception as e:
            print(f"Failed to acquire token: {e}")
            raise

    def get_auth_endpoint(self, resource_id: str) -> str:
        return (
            "https://management.azure.com/.default"
            if "azureml" in resource_id.lower()
            else f"{resource_id}/.default"
        )

    def get_token(self) -> str:
        return self._access_token 

    def request(
        self,
        request_type: str,
        url: str,
        accept: str = "application/json",
        payload: Optional[Union[dict, list]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": f"Omnia Timeseries SDK/{version} {system_version_string}",
        }

        return _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)