"""Small, read-only Mercedes mobile API client. No dependency on Home Assistant.

The private Mercedes API may change at any time. OAuth access and refresh tokens
are obtained separately; this module never handles account passwords.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, MutableMapping

import requests

EU_REST = 'https://bff.emea-prod.mobilesdk.mercedes-benz.com'
EU_WIDGET = 'https://widget.emea-prod.mobilesdk.mercedes-benz.com'
EU_LOGIN = 'https://id.mercedes-benz.com'
CLIENT_ID = '62778dc4-1de3-44f4-af95-115f06a3a008'
USER_AGENT = 'Mercedes-Benz/3044 CFNetwork/3860.400.22 Darwin/25.3.0'


class MercedesAPIError(RuntimeError):
    """Mercedes request failed."""


class MercedesAPI:
    """API access with token-store support and automatic refresh."""

    def __init__(self, tokens: MutableMapping[str, Any], session: requests.Session | None = None,
                 locale: str = 'de-DE') -> None:
        self.tokens = tokens
        self.session = session or requests.Session()
        self.locale = locale
        self._lock = threading.RLock()
        self._session_id = str(uuid.uuid4()).upper()

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.tokens["access_token"]}',
            'X-SessionId': self._session_id,
            'X-TrackingId': str(uuid.uuid4()).upper(),
            'ris-os-name': 'ios',
            'ris-os-version': '26.3',
            'Ris-Sdk-Version': '4.20.1',
            'Ris-Application-Version': '1.73.0',
            'X-Applicationname': 'mycar-store-ece',
            'X-Locale': self.locale,
            'Accept-Language': self.locale,
            'User-Agent': USER_AGENT,
            'Content-Type': 'application/json; charset=UTF-8',
        }

    def _refresh(self) -> None:
        old = self.tokens.get('refresh_token')
        if not old:
            raise MercedesAPIError('No refresh token available: external Mercedes login required')
        # Keep the refresh flow in line with mbapi2020/oauth.py: /v1/config preflight.
        preflight = self.session.get(EU_REST + '/v1/config', headers={
            k: v for k, v in self._headers().items() if k != 'Authorization'
        }, timeout=20)
        preflight.raise_for_status()
        response = self.session.post(EU_LOGIN + '/as/token.oauth2',
                                     data={'grant_type': 'refresh_token', 'refresh_token': old},
                                     headers={
                                         'User-Agent': USER_AGENT,
                                         'Ris-Os-Name': 'ios',
                                         'Ris-Os-Version': '26.3',
                                         'Ris-Sdk-Version': '4.20.1',
                                         'Ris-Application-Version': '1.73.0',
                                         'X-Applicationname': 'mycar-store-ece',
                                         'X-Device-Id': self.tokens.get('device_guid', str(uuid.uuid4())),
                                         'X-Request-Id': str(uuid.uuid4()),
                                     }, timeout=30)
        response.raise_for_status()
        new = response.json()
        if not new.get('access_token'):
            raise MercedesAPIError('Refresh response has no access_token')
        self.tokens.update(new)
        self.tokens['refresh_token'] = new.get('refresh_token', old)
        self.tokens['expires_at'] = time.time() + float(new.get('expires_in', 3600))

    def _authorized_get(self, url: str, *, binary: bool = False) -> Any:
        with self._lock:
            if not self.tokens.get('access_token') or (self.tokens.get('expires_at') is not None and time.time() > float(self.tokens['expires_at']) - 60):
                self._refresh()
            response = self.session.get(url, headers=self._headers(), timeout=30)
            if response.status_code == 401:
                self._refresh()
                response = self.session.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            return response.content if binary else response.json()

    def vehicles(self) -> Any:
        """Return /v2/vehicles JSON."""
        return self._authorized_get(EU_REST + '/v2/vehicles')

    def vehicle_status(self, vin: str) -> bytes:
        """Return VehicleStatusUpdate protobuf bytes (not VEPUpdate)."""
        if not isinstance(vin, str) or len(vin) != 17 or not vin.isalnum():
            raise ValueError('Invalid VIN')
        return self._authorized_get(EU_WIDGET + f'/v1/vehicle/{vin}/vehicleattributes', binary=True)
