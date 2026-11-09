"""Mercedes VehicleStatusUpdate -> normalized data.

The Mercedes protobufs can be downloaded at a pinned upstream revision
using scripts/vendor_mbapi_protos.py. Missing definitions are an error.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.protobuf.json_format import MessageToDict


def parse_status(payload: bytes, message_class: type) -> dict[str, Any]:
    """Decode exactly the VehicleStatusUpdate type from mbapi2020."""
    if not payload:
        raise ValueError('Empty Mercedes vehicle status response')
    msg = message_class()
    msg.ParseFromString(payload)
    data = MessageToDict(msg, preserving_proto_field_name=True)
    if not isinstance(data, dict):
        raise ValueError('Invalid vehicle status protobuf')
    return data


def _read(node: dict[str, Any], *names: str) -> tuple[Any, datetime | None]:
    """Get scalar value and original car timestamp, respecting status."""
    for name in names:
        item = node.get(name)
        if not isinstance(item, dict):
            continue
        metadata = item.get('metadata') or {}
        if metadata.get('status') in ('VALUE_INVALID', 'VALUE_NOT_AVAILABLE', 'VALUE_NOT_RECEIVED'):
            continue
        value = item.get('value')
        if value is None or isinstance(value, (list, dict)):
            continue
        measured = None
        stamp = metadata.get('timestamp')
        if stamp:
            try:
                measured = datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass
        return value, measured
    return None, None


def _numeric(raw: tuple[Any, datetime | None]) -> tuple[float | None, datetime | None]:
    """Convert protobuf int64 strings into numbers without inventing defaults."""
    value, measured = raw
    if isinstance(value, bool) or value is None:
        return None, measured
    try:
        return float(value), measured
    except (TypeError, ValueError, OverflowError):
        return None, measured


def normalize(payload: dict[str, Any]) -> dict[str, tuple[Any, datetime | None]]:
    """Preserve missing values and vehicle measurement timestamps."""
    return {
        'odometer': _numeric(_read(payload, 'odo')),
        'soc': _numeric(_read(payload, 'soc')),
        'electric_range': _numeric(_read(payload, 'rangeelectric')),
        'fuel_range': _numeric(_read(payload, 'rangeliquid', 'gas_tank_range', 'gasTankRange')),
        'latitude': _numeric(_read(payload, 'position_lat')),
        'longitude': _numeric(_read(payload, 'position_long')),
        'outside_temperature': _numeric(_read(payload, 'outside_temperature')),
    }
