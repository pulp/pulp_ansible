import asyncio
import json

from gettext import gettext as _
from logging import getLogger

from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientResponseError

from pulpcore.plugin.download import DownloaderFactory, FileDownloader, HttpDownloader


log = getLogger(__name__)


class AnsibleFileDownloader(FileDownloader):
    """
    FileDownloader that strips out Ansible's custom http downloader arguments.

    This is unfortunate, but there isn't currently a good pattern for customizing the downloader
    factory machinery such that certain types of arguments only apply to certain downloaders,
    so passing a kwarg into get_downloader() will pass it to constructor for any downloader.

    TODO: https://pulp.plan.io/issues/7352
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the downloader.
        """
        kwargs.pop("silence_errors_for_response_status_codes", None)
        super().__init__(*args, **kwargs)


AUTH_TOKEN = None
TOKEN_LOCK = asyncio.Lock()


class TokenAuthHttpDownloader(HttpDownloader):
    """
    Custom Downloader that automatically handles Token Based and Basic Authentication.
    """

    def __init__(
        self, url, auth_url, token, silence_errors_for_response_status_codes=None, **kwargs
    ):
        """
        Initialize the downloader.
        """
        self.ansible_auth_url = auth_url
        self.token = token
        if silence_errors_for_response_status_codes is None:
            silence_errors_for_response_status_codes = set()
        self.silence_errors_for_response_status_codes = silence_errors_for_response_status_codes
        super().__init__(url, **kwargs)

    def raise_for_status(self, response):
        """
        Raise error if aiohttp response status is >= 400 and not silenced.

        Raises:
            FileNotFoundError: If aiohttp response status is 404 and silenced.
            aiohttp.ClientResponseError: If the response status is 400 or higher and not silenced.

        """
        silenced = response.status in self.silence_errors_for_response_status_codes

        if not silenced:
            response.raise_for_status()

        if response.status == 404:
            raise FileNotFoundError()

    async def _run(self, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        This method is decorated with a backoff-and-retry behavior to retry HTTP 429 errors. It
        retries with exponential backoff 10 times before allowing a final exception to be raised.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.

        """
        if not self.token and not self.ansible_auth_url:
            return await super()._run(extra_data=extra_data)
        elif self.token and not self.ansible_auth_url:
            # https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
            headers = {"Authorization": "Token {token}".format(token=self.token)}
            return await self._run_with_additional_headers(headers)
        else:
            return await self._run_with_token_refresh_and_401_retry()

    async def _run_with_token_refresh_and_401_retry(self):
        """
        Fetch the response and refresh the Keycloak token if needed when doing so.

        If the fetching of data returns a 401 exception, invalidate the token and try to refresh it
        once again.

        Returns:
            DownloadResult: Contains information about the result. See the DownloadResult docs for
                 more information.
        """
        while True:
            token = await self.get_or_update_token()
            # Keycloak Token
            headers = {"Authorization": "Bearer {token}".format(token=token)}
            try:
                return await self._run_with_additional_headers(headers)
            except ClientResponseError as exc:
                if exc.status == 401:
                    global AUTH_TOKEN
                    AUTH_TOKEN = None  # The token expired so let's forget it so it will refresh
                    continue
                else:
                    raise

    async def _run_with_additional_headers(self, headers):
        """
        Fetch the response and submit additional headers.

        Args:
            headers: Additional headers to submit.

        Returns:
            DownloadResult: Contains information about the result. See the DownloadResult docs for
                 more information.
        """
        if self.download_throttler:
            await self.download_throttler.acquire()
        async with self.session.get(
            self.url, headers=headers, proxy=self.proxy, proxy_auth=self.proxy_auth, auth=self.auth
        ) as response:
            self.raise_for_status(response)
            to_return = await self._handle_response(response)
            await response.release()

        if self._close_session_on_finalize:
            self.session.close()
        return to_return

    async def get_or_update_token(self):
        """
        Use an existing, or refresh, the Bearer token to be used with all requests.
        """
        global AUTH_TOKEN
        global TOKEN_LOCK

        if AUTH_TOKEN:
            return AUTH_TOKEN
        async with TOKEN_LOCK:
            if AUTH_TOKEN:
                return AUTH_TOKEN
            log.info(_("Updating bearer token"))
            form_payload = {
                "grant_type": "refresh_token",
                "client_id": "cloud-services",
                "refresh_token": self.token,
            }
            url = self.ansible_auth_url
            async with self.session.post(
                url,
                data=form_payload,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                auth=self.auth,
                raise_for_status=True,
            ) as response:
                token_data = await response.text()

            AUTH_TOKEN = json.loads(token_data)["access_token"]
            return AUTH_TOKEN


class AnsibleDownloaderFactory(DownloaderFactory):
    """A factory for creating downloader objects that are configured from with remote settings."""

    def __init__(self, remote, downloader_overrides=None):
        """
        Initialize AnsibleDownloaderFactory.

        Args:
            remote (:class:`~pulpcore.plugin.models.Remote`): The remote used to populate
                downloader settings.
            downloader_overrides (dict): Keyed on a scheme name, e.g. 'https' or 'ftp' and the value
                is the downloader class to be used for that scheme, e.g.
                {'https': MyCustomDownloader}. These override the default values.
        """
        if not downloader_overrides:
            downloader_overrides = {
                "http": TokenAuthHttpDownloader,
                "https": TokenAuthHttpDownloader,
                "file": AnsibleFileDownloader,
            }
        super().__init__(remote, downloader_overrides)

    def _http_or_https(self, download_class, url, **kwargs):
        """
        Build a downloader for http:// or https:// URLs.

        Args:
            download_class (:class:`~pulpcore.plugin.download.BaseDownloader`): The download
                class to be instantiated.
            url (str): The download URL.
            kwargs (dict): All kwargs are passed along to the downloader. At a minimum, these
                include the :class:`~pulpcore.plugin.download.BaseDownloader` parameters.

        Returns:
            :class:`~pulpcore.plugin.download.HttpDownloader`: A downloader that
            is configured with the remote settings.

        """
        options = {"session": self._session}
        if self._remote.proxy_url:
            options["proxy"] = self._remote.proxy_url
            if self._remote.proxy_username and self._remote.proxy_password:
                options["proxy_auth"] = BasicAuth(
                    login=self._remote.proxy_username, password=self._remote.proxy_password
                )

        if not self._remote.token and self._remote.username and self._remote.password:
            options["auth"] = BasicAuth(login=self._remote.username, password=self._remote.password)

        kwargs["throttler"] = self._remote.download_throttler if self._remote.rate_limit else None

        return download_class(url, self._remote.auth_url, self._remote.token, **options, **kwargs)
