import time

import httpx
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from tqdm import tqdm

from parse.logger import create_logger


class GraphQLClient:
    """
    A client for interacting with a GraphQL API, supporting authentication and query execution.
    """

    def __init__(self, url: str, client_id: str, client_secret: str, timeout: float = 1.0) -> None:
        self._logger = create_logger(component="GraphQLClient")

        self._timeout = timeout
        self._auth_url = f"{url}/oauth/token"
        self._graphql_url = f"{url}/api/graphql"

        # general client constants. See in more details shiki OAuth2 Guide::
        # https://shikimori.one/oauth?oauth_application_id=15
        self._auth_headers = {
            "User-Agent": "shikimori-parser",
        }
        self._token_auth_params = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        self._client = None

    def get_access_token(self, auth_code: str) -> httpx.Response:
        """
        Obtain an access token using an authorization code. See in more details shiki OAuth2 Guide:
        https://shikimori.one/oauth?oauth_application_id=15

        Parameters
        ----------
        auth_code : str
            The authorization code obtained from the OAuth2 flow.
        """
        with httpx.Client() as client:
            try:
                response = client.post(
                    url=self._auth_url,
                    data=self._get_auth_params(auth_code),
                    headers=self._auth_headers,
                )

                if response.status_code != 200:
                    raise httpx.RequestError(f"Authorization failed: {response.text}")

                return response

            except httpx.RequestError as e:
                raise httpx.RequestError(
                    f"An error occurred while requesting auth code: {e}"
                )

    def get_anime_count(self) -> int:
        base_url = self._auth_url.replace("/oauth/token", "")
        limit = 50

        def _page_size(page: int) -> int:
            with httpx.Client() as client:
                response = client.get(
                    url=f"{base_url}/api/animes",
                    params={"limit": limit, "censored": "false", "order": "id", "page": page},
                    headers=self._auth_headers,
                )
                return len(response.json())

        lo, hi = 1, 2000
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _page_size(mid) > 0:
                lo = mid
            else:
                hi = mid - 1

        return (lo - 1) * limit + _page_size(lo)

    def refresh_access_token(self, refresh_token: str) -> httpx.Response:
        """
        Refresh an expired authentication token. See in more details shiki OAuth2 Guide:
        https://shikimori.one/oauth?oauth_application_id=15

        Parameters
        ----------
        refresh_token : str
            The refresh token used to obtain a new authentication token.
        """
        with httpx.Client() as client:
            try:
                response = client.post(
                    url=self._auth_url,
                    data=self._get_refresh_params(refresh_token),
                    headers=self._auth_headers,
                )

                if response.status_code != 200:
                    raise httpx.RequestError(
                        f"Failed to refresh token: {response.text}"
                    )

                return response

            except httpx.RequestError as e:
                raise httpx.RequestError(
                    f"An error occurred while requesting refresh token: {e}"
                )

    def init(self, access_token: str) -> None:
        """
        Initialize the GraphQL client with an authentication token.

        Parameters
        ----------
        access_token : str
            The authentication access token to authorize the client.
        """
        transport = self._get_transport(access_token)
        self._client = Client(transport=transport, fetch_schema_from_transport=True)

    def execute(
        self, query: str, variables: dict[str, any] | None = None, max_pages: int = 1
    ) -> list[dict]:
        """
        Execute a GraphQL query, paginating through the results if necessary.

        Parameters
        ----------
        query : str
            The GraphQL query string.
        variables : dict[str, any], optional
            A dictionary of variables for the query, by default None.
        max_pages : int
            The maximum number of pages to fetch (default is 1).
            Your query must support page PositiveInt param (check examples).
        """
        if variables is None:
            variables = {}

        page_to_start = variables.get("page", 1)

        start_time = time.time()
        all_results = []

        with tqdm(total=max_pages, desc="Fetching pages", unit="page") as bar:
            for page in range(page_to_start, page_to_start + max_pages):
                # litle timeout sleep for a limiter
                time.sleep(self._timeout)

                variables["page"] = page
                try:
                    result = self._client.execute(gql(query), variable_values=variables)
                    for key, value in result.items():
                        if isinstance(value, list):
                            all_results.extend(value)
                        else:
                            self._logger.warning(
                                f"Unexpected structure for key '{key}', skipping."
                            )

                    if not result or all(not value for value in result.values()):
                        self._logger.info(f"No more data found, stopping at page {page}.")
                        break

                    bar.set_postfix(anime=len(all_results))
                    bar.update(1)

                except Exception as e:
                    self._logger.error(f"Error while fetching page {page}: {e}")
                    continue

        self._logger.info(
            f"Execution completed in {time.time() - start_time:.2f} seconds"
        )
        return all_results

    def _get_auth_params(self, auth_code: str) -> dict[str, str]:
        auth_params = self._token_auth_params.copy()
        auth_params["grant_type"] = "authorization_code"
        auth_params["code"] = auth_code
        auth_params["redirect_uri"] = "urn:ietf:wg:oauth:2.0:oob"
        return auth_params

    def _get_refresh_params(self, refresh_token: str) -> dict[str, str]:
        refresh_params = self._token_auth_params.copy()
        refresh_params["grant_type"] = "refresh_token"
        refresh_params["refresh_token"] = refresh_token
        return refresh_params

    def _get_transport(self, token: str) -> AIOHTTPTransport:
        headers = self._auth_headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        return AIOHTTPTransport(url=self._graphql_url, headers=headers, ssl=True)
