import asyncio
import backoff
import json
import ssl
from tempfile import NamedTemporaryFile

from gettext import gettext as _
from logging import getLogger

import aiohttp
from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientResponseError

from pulpcore.download.factory import user_agent
from pulpcore.plugin.download import (
    http_giveup,
    DownloaderFactory,
    FileDownloader,
    HttpDownloader,
)


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
AUTOHUB_LIMIT_PER_HOST = 2


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

    @backoff.on_exception(backoff.expo, ClientResponseError, max_tries=10, giveup=http_giveup)
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
            headers = {"Authorization": "Bearer {token}".format(token=self.token)}
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
        await asyncio.sleep(0.2)
        async with self.session.get(self.url, headers=headers, proxy=self.proxy) as response:
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
            async with self.session.post(url, data=form_payload, raise_for_status=True) as response:
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

    # cut and paste from DownloadFactory and tweaked.
    def _make_aiohttp_session_from_remote(self):
        """
        Build a :class:`aiohttp.ClientSession` from the remote's settings and timing settings.

        This method does not force_close of the TCP connection with each request.
        This method also sets a TCPConnect() limit_per_host.

        Returns:
            :class:`aiohttp.ClientSession`
        """
        tcp_conn_opts = {"force_close": False}

        sslcontext = None
        if self._remote.ca_cert:
            sslcontext = ssl.create_default_context(cadata=self._remote.ca_cert)
        if self._remote.client_key and self._remote.client_cert:
            if not sslcontext:
                sslcontext = ssl.create_default_context()
            with NamedTemporaryFile() as key_file:
                key_file.write(bytes(self._remote.client_key, "utf-8"))
                key_file.flush()
                with NamedTemporaryFile() as cert_file:
                    cert_file.write(bytes(self._remote.client_cert, "utf-8"))
                    cert_file.flush()
                    sslcontext.load_cert_chain(cert_file.name, key_file.name)
        if not self._remote.tls_validation:
            if not sslcontext:
                sslcontext = ssl.create_default_context()
            sslcontext.check_hostname = False
            sslcontext.verify_mode = ssl.CERT_NONE
        if sslcontext:
            tcp_conn_opts["ssl_context"] = sslcontext

        headers = {"User-Agent": user_agent()}

        tcp_conn_opts["limit_per_host"] = AUTOHUB_LIMIT_PER_HOST

        conn = aiohttp.TCPConnector(**tcp_conn_opts)

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=600, sock_read=600)
        return aiohttp.ClientSession(connector=conn, timeout=timeout, headers=headers)

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

        if not self._remote.token and self._remote.username and self._remote.password:
            options["auth"] = BasicAuth(login=self._remote.username, password=self._remote.password)

        return download_class(url, self._remote.auth_url, self._remote.token, **options, **kwargs)
