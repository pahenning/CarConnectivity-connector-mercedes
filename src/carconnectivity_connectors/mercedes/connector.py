"""CarConnectivity Mercedes connector, conservative read-only prototype."""
from __future__ import annotations

import logging
import threading
import traceback
from datetime import timedelta
from typing import Any

from carconnectivity.attributes import DurationAttribute, EnumAttribute
from carconnectivity.drive import ElectricDrive, CombustionDrive
from carconnectivity.enums import ConnectionState
from carconnectivity.errors import AuthenticationError, RetrievalError, TooManyRequestsError
from carconnectivity.units import Length, Temperature
from carconnectivity.vehicle import GenericVehicle, ElectricVehicle
from carconnectivity_connectors.base.connector import BaseConnector

from .api import MercedesAPI
from .parser import normalize, parse_status

LOG = logging.getLogger('carconnectivity.connectors.mercedes')
LOG_API = logging.getLogger('carconnectivity.connectors.mercedes-api-debug')


class Connector(BaseConnector):
    """Read vehicle information without Mercedes remote commands."""

    def __init__(self, connector_id: str, car_connectivity: Any, config: dict[str, Any], *args,
                 initialization: dict[str, Any] | None = None, **kwargs) -> None:
        super().__init__(connector_id=connector_id, car_connectivity=car_connectivity, config=config,
                         log=LOG, api_log=LOG_API, *args, initialization=initialization, **kwargs)
        self._stop_event = threading.Event()
        self._background_thread: threading.Thread | None = None
        self.active_config['interval'] = int(config.get('interval', 300))
        if self.active_config['interval'] < 300:
            raise ValueError('Minimum interval is 300 seconds')
        self.interval = DurationAttribute(name='interval', parent=self, tags={'connector_custom'})
        self.interval.minimum = timedelta(seconds=300)
        self.interval._is_changeable = True
        self.interval._set_value(value=timedelta(seconds=self.active_config['interval']))
        self.connection_state = EnumAttribute(name='connection_state', parent=self,
                                             value_type=ConnectionState, value=ConnectionState.DISCONNECTED,
                                             tags={'connector_custom'})

        # OAuth2 password/PKCE flow is not yet part of this prototype. Tokens may
        # come from the standard CC token store or configuration for first start.
        store = self.car_connectivity.get_tokenstore()
        self._token_key = 'carconnectivity-connector-mercedes:' + config.get('account', 'default')
        # Only use JSON tokens for the initial bootstrap. Never replace a
        # refreshed token from the persistent store with stale config values.
        saved_tokens = store.get(self._token_key)
        if isinstance(saved_tokens, dict) and saved_tokens.get('refresh_token'):
            self._tokens = dict(saved_tokens)
        else:
            self._tokens = {}
            for field in ('access_token', 'refresh_token', 'expires_at', 'device_guid'):
                if config.get(field) is not None:
                    self._tokens[field] = config[field]
        if not self._tokens.get('refresh_token') and not self._tokens.get('access_token'):
            raise AuthenticationError('Mercedes OAuth tokens missing. See README.md for bootstrap.')
        self._api = MercedesAPI(self._tokens, locale=config.get('locale', 'de-DE'))
        self._proto_class: type | None = None

    @staticmethod
    def _load_proto() -> type:
        # Pinned, MIT-licensed generated protobuf files are vendored by script.
        try:
            from .proto import vehicle_events_pb2 as module  # pylint: disable=import-outside-toplevel
            return module.VehicleStatusUpdate
        except (ImportError, AttributeError) as err:
            raise RetrievalError('Mercedes protobuf files missing: run python scripts/vendor_mbapi_protos.py before installation.') from err

    def startup(self) -> None:
        self._background_thread = threading.Thread(target=self._background_loop, daemon=False,
                                                   name='carconnectivity.connectors.mercedes-background')
        self._background_thread.start()

    def _background_loop(self) -> None:
        self.connection_state._set_value(value=ConnectionState.CONNECTING)
        while not self._stop_event.is_set():
            try:
                self.fetch_all()
                self.healthy._set_value(value=True)
                self.connection_state._set_value(value=ConnectionState.CONNECTED)
            except Exception:
                LOG.error('Mercedes fetch failed: %s', traceback.format_exc())
                self.healthy._set_value(value=False)
                self.connection_state._set_value(value=ConnectionState.ERROR)
            self._stop_event.wait(self.active_config['interval'])

    @staticmethod
    def _find_vehicles(data: Any) -> list[dict[str, Any]]:
        """Only accept explicit VIN-bearing list entries, never manufacture VINs."""
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = next((data[k] for k in ('vehicles', 'data', 'items') if isinstance(data.get(k), list)), [])
        else:
            items = []
        return [v for v in items if isinstance(v, dict) and
                isinstance(v.get('vin') or v.get('fin'), str) and len(v.get('vin') or v.get('fin')) == 17]

    def _persist(self) -> None:
        self.car_connectivity.get_tokenstore()[self._token_key] = dict(self._tokens)

    def fetch_all(self) -> None:
        if self._proto_class is None:
            self._proto_class = self._load_proto()
        try:
            data = self._api.vehicles()
            for entry in self._find_vehicles(data):
                vin = entry.get('vin') or entry['fin']
                try:
                    payload = self._api.vehicle_status(vin)
                    parsed = parse_status(payload, self._proto_class)
                    if parsed.get('fin_or_vin') != vin:
                        raise ValueError('VehicleStatusUpdate VIN does not match requested VIN')
                    self._update_vehicle(vin, entry, normalize(parsed))
                except Exception as err:
                    LOG.warning('Could not update vehicle %s: %s', vin[:5] + '********' + vin[-4:], err)
        except Exception as err:
            status = getattr(getattr(err, 'response', None), 'status_code', None)
            if status in (401, 403):
                raise AuthenticationError('Mercedes API access rejected') from err
            if status == 429:
                raise TooManyRequestsError('Mercedes API request limit reached') from err
            raise RetrievalError('Mercedes vehicle list retrieval failed') from err
        finally:
            self._persist()

    @staticmethod
    def _set(attribute: Any, value: Any, measured: Any = None, unit: Any = None) -> None:
        if attribute is None or value is None:
            return
        kwargs = {'value': value}
        if measured is not None:
            kwargs['measured'] = measured
        if unit is not None:
            kwargs['unit'] = unit
        attribute._set_value(**kwargs)

    def _update_vehicle(self, vin: str, meta: dict[str, Any],
                        values: dict[str, tuple[Any, Any]]) -> None:
        garage = self.car_connectivity.garage
        vehicle = garage.get_vehicle(vin)
        is_electric = values['soc'][0] is not None or values['electric_range'][0] is not None
        if vehicle is None:
            vehicle = (ElectricVehicle if is_electric else GenericVehicle)(
                vin=vin, garage=garage, managing_connector=self)
            garage.add_vehicle(vin, vehicle)
        self._set(vehicle.manufacturer, 'Mercedes-Benz')
        model = meta.get('model') or meta.get('modelName')
        if isinstance(model, str):
            self._set(vehicle.model, model)
        plate = meta.get('licensePlate') or meta.get('licenseplate')
        if isinstance(plate, str):
            self._set(vehicle.license_plate, plate)
        self._set(vehicle.odometer, *values['odometer'], unit=Length.KM)
        self._set(vehicle.outside_temperature, *values['outside_temperature'], unit=Temperature.C)
        if vehicle.position is not None:
            self._set(vehicle.position.latitude, *values['latitude'])
            self._set(vehicle.position.longitude, *values['longitude'])
        if isinstance(vehicle, ElectricVehicle) and vehicle.drives is not None:
            drive = next((d for d in vehicle.drives.drives.values() if isinstance(d, ElectricDrive)), None)
            if drive is None:
                drive = ElectricDrive(drive_id='electric', drives=vehicle.drives)
                vehicle.drives.add_drive(drive)
            self._set(drive.level, *values['soc'])
            self._set(drive.range, *values['electric_range'], unit=Length.KM)
        if values['fuel_range'][0] is not None and vehicle.drives is not None:
            drive = next((d for d in vehicle.drives.drives.values() if isinstance(d, CombustionDrive)), None)
            if drive is None:
                drive = CombustionDrive(drive_id='combustion', drives=vehicle.drives)
                vehicle.drives.add_drive(drive)
            self._set(drive.range, *values['fuel_range'], unit=Length.KM)

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._background_thread:
            self._background_thread.join(timeout=10)
        self._persist()
        self.connection_state._set_value(value=ConnectionState.DISCONNECTED)

    def get_version(self) -> str:
        return '0.1.0a1'

    def get_type(self) -> str:
        return 'mercedes'
