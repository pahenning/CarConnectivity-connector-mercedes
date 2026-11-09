#!/usr/bin/env python3
"""Fetch a pinned set of upstream generated Mercedes protobuf modules.

Run explicitly from the repository root before building the wheel.
The fetched source is MIT licensed; see LICENSE.mbapi2020.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import urllib.request

UPSTREAM_COMMIT = '79b9e0cd2a450b0bf7466bc7d5e9d7682d83b0bb'
UPSTREAM_FILES = (
    'acp_pb2.py', 'client_pb2.py', 'cluster_pb2.py',
    'eventpush_pb2.py', 'gogo_pb2.py', 'protos_pb2.py',
    'service_activation_pb2.py', 'user_events_pb2.py',
    'vehicle_commands_pb2.py', 'vehicle_events_pb2.py',
    'vehicleapi_pb2.py', 'vin_events_pb2.py',
)


def rewrite_imports(data: str) -> str:
    """Generated absolute Home Assistant imports -> package-relative imports."""
    return re.sub(
        r'^import custom_components\.mbapi2020\.proto\.([a-z0-9_]+_pb2) as ([a-z0-9_]+)$',
        r'from . import \1 as \2', data, flags=re.MULTILINE,
    )


def download(name: str, *, revision: str = UPSTREAM_COMMIT) -> str:
    url = f'https://raw.githubusercontent.com/ReneNulschDE/mbapi2020/{revision}/custom_components/mbapi2020/proto/{name}'
    with urllib.request.urlopen(url, timeout=30) as response:  # nosec: pinned public source
        return response.read().decode('utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overwrite', action='store_true', help='replace existing generated modules')
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    target = root / 'src/carconnectivity_connectors/mercedes/proto'
    target.mkdir(parents=True, exist_ok=True)
    files = {name: rewrite_imports(download(name)) for name in UPSTREAM_FILES}
    for name, content in files.items():
        # The generated code must not retain Home Assistant-specific imports.
        if 'custom_components.mbapi2020.proto.' in content:
            raise SystemExit(f'Unconverted import in {name}: upstream structure changed')
        file = target / name
        if file.exists() and not args.overwrite:
            raise SystemExit(f'{file} exists; use --overwrite to replace all modules')
    for name, content in files.items():
        (target / name).write_text(content, encoding='utf-8')
        print(f'Wrote {target / name}')
    print(f'Installed {len(files)} generated modules from {UPSTREAM_COMMIT}')


if __name__ == '__main__':
    main()
