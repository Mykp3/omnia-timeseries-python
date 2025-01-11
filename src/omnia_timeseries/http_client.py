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

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")

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
        self._access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        is_kubernetes_env = os.getenv("KUBERNETES_SERVICE_HOST")
        resource_id = self._resource_id
        if "azureml" in resource_id.lower():
            auth_endpoint = "https://management.azure.com/.default"
            print("🔧 Using generic auth endpoint for AzureML resource due to network restrictions")
        else:
            auth_endpoint = f"{resource_id}/.default"

        client_id = os.getenv("AZURE_CLIENT_ID")
        if not client_id:
            raise ValueError("AZURE_CLIENT_ID environment variable is not set.")

        try:
            if is_kubernetes_env:
                print(f"Using ManagedIdentityCredential with client_id: {client_id}")
                azure_credential = ManagedIdentityCredential(client_id=client_id)
            else:
                print("Using DefaultAzureCredential")
                azure_credential = DefaultAzureCredential()

            token = azure_credential.get_token(auth_endpoint).token
            print(f"Successfully retrieved token: {token[:10]}...")
            return token

        except Exception as e:
            print(f"Error fetching token for {auth_endpoint}: {str(e)}")
            raise

    def refresh_token(self):
        """Refresh the access token."""
        print("🔄 Refreshing access token...")
        self._access_token = self._get_access_token()

    def request(
        self,
        request_type: str,
        url: str,
        accept: str = "application/json",
        payload: Optional[Union[dict, list]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a request with the current access token."""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": f"Omnia Timeseries SDK/{version} {system_version_string}",
        }

        response = _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)


        if response.status_code == 401:
            print("Unauthorized. Attempting to refresh the token and retry...")
            self.refresh_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)

        return response
