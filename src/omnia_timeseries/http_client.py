from typing import Literal, Optional, TypedDict, Union, Dict, Any
import requests
import logging
from azure.identity import ManagedIdentityCredential
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


from azure.identity import ManagedIdentityCredential

class HttpClient:
    def __init__(self, resource_id: str, azure_credential=None, client_id=None):
        """
        Initializes the HttpClient class.

        :param resource_id: The resource ID for which to obtain the access token.
        :param azure_credential: Accepted but ignored. Kept for backward compatibility.
        :param client_id: Accepted but ignored. Kept for backward compatibility.
        """
        self._resource_id = resource_id
        self._client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        if not self._client_id:
            raise ValueError("AZURE_CLIENT_ID environment variable is not set.")
        self._access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        """
        Retrieves an access token using ManagedIdentityCredential only.

        :return: Access token as a string.
        """
        resource_id = self._resource_id
        auth_endpoint = "https://management.azure.com/.default" if "ml" in resource_id.lower() else f"{resource_id}/.default"

        print(f"🔧 Forcing use of ManagedIdentityCredential with client_id: {self._client_id}")
        try:
            # Force the use of ManagedIdentityCredential ONLY, no fallback
            azure_credential = ManagedIdentityCredential(client_id=self._client_id)
            token = azure_credential.get_token(auth_endpoint).token
            print(f"✅ Successfully retrieved token: {token[:10]}...")
            return token

        except Exception as e:
            print(f"❌ Error fetching token: {e}")
            raise

    def request(
        self,
        request_type: str,
        url: str,
        accept: str = "application/json",
        payload: Optional[Union[dict, list]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Makes an HTTP request using the current access token.

        :param request_type: The type of HTTP request (GET, POST, etc.).
        :param url: The request URL.
        :param accept: The 'Accept' header value.
        :param payload: The request payload (for POST/PUT requests).
        :param params: Query parameters for the request.
        :return: The response from the HTTP request.
        """
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": f"Omnia Timeseries SDK/{version} {system_version_string}",
        }

        response = _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)

        # If unauthorized, refresh the token and retry
        if response.status_code == 401:
            print("🔐 Unauthorized. Attempting to refresh the token and retry...")
            self._access_token = self._get_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = _request(request_type=request_type, url=url, headers=headers, payload=payload, params=params)

        return response


