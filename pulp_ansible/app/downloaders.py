from logging import getLogger
import asyncio
import backoff
import json

from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientResponseError

from pulpcore.plugin.download import http_giveup, DownloaderFactory, HttpDownloader


log = getLogger(__name__)


class TokenAuthHttpDownloader(HttpDownloader):
    """
    Custom Downloader that automatically handles Token Based and Basic Authentication.
    """

    TOKEN_LOCK = asyncio.Lock()

    def __init__(self, url, auth_url, token, **kwargs):
        """
        Initialize the downloader.
        """
        self.ansible_auth_url = auth_url
        self.ansible_token = token
        super().__init__(url, **kwargs)

    @backoff.on_exception(backoff.expo, ClientResponseError, max_tries=10, giveup=http_giveup)
    async def _run(self, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        This method is decorated with a backoff-and-retry behavior to retry HTTP 429 errors. It
        retries with exponential backoff 10 times before allowing a final exception to be raised.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.

        Ansible token reference:
            https://github.com/ansible/ansible/blob/devel/lib/ansible/galaxy/token.py

        """
        if not self.ansible_token:
            # No Token
            return await super()._run(extra_data=extra_data)

        if not self.ansible_auth_url:
            # Galaxy Token
            headers = {"Authorization": self.ansible_token}
        else:
            token = await self.update_token_from_auth_url()
            # Keycloak Token
            headers = {"Authorization": "Bearer {token}".format(token=token)}

        async with self.session.get(self.url, headers=headers, proxy=self.proxy) as response:
            response.raise_for_status()
            to_return = await self._handle_response(response)
            await response.release()

        if self._close_session_on_finalize:
            self.session.close()
        return to_return

    async def update_token_from_auth_url(self):
        """
        Update the Bearer token to be used with all requests.
        """
        async with self.TOKEN_LOCK:
            log.info("Updating bearer token")
            form_payload = {
                "grant_type": "refresh_token",
                "client_id": "cloud-services",
                "refresh_token": self.ansible_token,
            }
            url = self.ansible_auth_url
            async with self.session.post(url, data=form_payload, raise_for_status=True) as response:
                token_data = await response.text()

            return json.loads(token_data)["access_token"]


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

        if not self._remote.token and self._remote.username and self._remote.password:
            options["auth"] = BasicAuth(login=self._remote.username, password=self._remote.password)

        return download_class(url, self._remote.auth_url, self._remote.token, **options, **kwargs)
