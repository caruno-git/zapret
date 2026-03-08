from packaging.version import Version
import requests, logging, json

log = logging.getLogger("zapret.updater")
VERSION_URL = "https://zapretdpi.ru/version.json"

class UpdateChecker:
    def __init__(self, channel: str, local_version: str):
        self.channel = channel
        self.local   = Version(local_version)

    def _fetch(self) -> dict | None:
        try:
            data = requests.get(VERSION_URL, timeout=10).json()
            return data.get(self.channel)
        except Exception as e:
            log.error("version.json fetch error: %s", e)
            return None

    def needs_update(self) -> dict | None:
        remote = self._fetch()
        if not remote:
            return None
        if Version(remote["version"]) > self.local:
            return remote
        return None
