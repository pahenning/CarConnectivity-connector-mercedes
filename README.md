# CarConnectivity Connector for Mercedes-Benz (experimental)

**Status: early, read-only prototype (0.1.0a1).** This repository is suitable for source-code development, but **the connector is not yet operational without additional setup**. It has not been verified against a real Mercedes-Benz account or vehicle. In particular, there is **no interactive Mercedes login**, no remote commands, and the matching protobuf modules are not included in the initial source archive.

This plugin follows the conventions of [CarConnectivity](https://github.com/tillsteinbach/CarConnectivity) and its [Renault/Dacia connector](https://github.com/pahenning/CarConnectivity-connector-renaultdacia). The Mercedes-specific private API endpoints and protobuf format are based on [ReneNulschDE/mbapi2020](https://github.com/ReneNulschDE/mbapi2020). It does **not** depend on Home Assistant at runtime.

## Current scope

- Plugin registration as `mercedes` using a Python entry point
- Background polling, default 300 seconds
- OAuth access/refresh tokens from CarConnectivity tokenstore (or initially via config)
- Vehicle discovery (`/v2/vehicles`)
- Read-only vehicle status via the binary `/v1/vehicle/{vin}/vehicleattributes` endpoint
- Mapping of VIN, manufacturer, model, registration plate, odometer, electric state of charge, electric/fuel range, outside temperature and GPS position (when exposed)
- Preserve measurement times provided by Mercedes; absent readings are **not** replaced with zero or an invented position

The prototype currently supports **Europe only**. It does not yet provide initial OAuth PKCE login / two-factor support, websocket push, remote lock/unlock, climatization, charge commands, or robust hybrid/drive classification. Rest-status polling exposes only a subset of the values available through mbapi2020 websocket push; absence of other attributes is expected. This is not a substitute for the full Mercedes app.

## Source layout

```text
src/carconnectivity_connectors/mercedes/
  __init__.py          package
  connector.py         CarConnectivity adapter and background worker
  api.py               standalone Mercedes REST client and token refresh
  parser.py            binary protobuf mapping and value normalization
  proto/               generated files: add with scripts/vendor_mbapi_protos.py
scripts/
  vendor_mbapi_protos.py
tests/
  test_parser.py
```

## Developer setup

Use Python **3.11 or later**.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

# Required once: fetch the MIT-licensed protobuf modules from the pinned
# mbapi2020 commit and fix their package-relative imports.
python scripts/vendor_mbapi_protos.py

# Install the plugin in your CarConnectivity Python environment.
python -m pip install -e .

# Offline unit tests (no Mercedes account necessary).
python -m unittest discover -s tests -v
```

The protobuf vendor script uses the **pinned upstream commit** `79b9e0cd2a450b0bf7466bc7d5e9d7682d83b0bb` and writes 12 generated `*_pb2.py` files to `src/carconnectivity_connectors/mercedes/proto/`. It does not run automatically on installation, so a source checkout can be inspected before fetching third-party code. The generated files may be committed to this repository after review. They originate from mbapi2020, which uses the MIT license reproduced in `LICENSE.mbapi2020`.

If upstream changes the protobuf format, review the new schema and parser before changing the pinned commit. Use `--overwrite` only when intentionally replacing all generated modules.

## Configuration

The following illustrates a connector block **after tokens have been obtained separately**. These are not working sample credentials:

```json
{
  "carConnectivity": {
    "connectors": [
      {
        "type": "mercedes",
        "config": {
          "account": "my-mercedes",
          "locale": "de-DE",
          "interval": 300,
          "access_token": "<valid-access-token>",
          "refresh_token": "<valid-refresh-token>",
          "expires_at": 1794210000
        }
      }
    ]
  }
}
```

**Do not commit the configuration containing tokens.** The `.gitignore` excludes typical configuration filenames, but it is safest to supply tokens directly through the CarConnectivity tokenstore under the key `carconnectivity-connector-mercedes:my-mercedes`. Tokens in the JSON configuration are only a temporary bootstrap mechanism. `expires_at` is a UNIX timestamp supplied as an example, not a valid token expiration. A full Mercedes account login will be added later and is required for routine end-user installation.

## Publishing the initial project to GitHub

If your repository already exists at `https://github.com/pahenning/CarConnectivity-connector-mercedes`, clone it and copy/extract the supplied source archive **into the repository root** (overwriting its placeholder README). Then:

```bash
cd CarConnectivity-connector-mercedes
# Optional but recommended before the first release:
python scripts/vendor_mbapi_protos.py
python -m unittest discover -s tests -v

git add .
git commit -m "Initial experimental Mercedes CarConnectivity connector"
git push origin main
```

The `git add .` step deliberately includes the generated protobuf files if you ran the vendor script. Do not add any account credentials or real vehicle status JSON to Git.

## Limitations and testing

- No Mercedes login / real-car integration test was performed.
- The private Mercedes API may change without notice. Some app identification headers are currently pinned to values from mbapi2020; dynamic app version detection is not implemented yet.
- Authorization errors and rate limiting require real API tests. Avoid polling below five minutes.
- The protobuf `VehicleStatusUpdate` is deliberately decoded with its real message class; it must not be confused with the older `VEPUpdate`.
- The status endpoint exposes only a limited set of attributes. Where Mercedes does not return GPS coordinates, the connector leaves the position unset.
- Do not publish captured requests/responses without removing VINs, locations, tokens, registration plates and personal information.

## License and acknowledgements

This connector's original adapter code is MIT-licensed (`LICENSE`). Optional generated protobuf modules fetched by the vendor script are derived from ReneNulschDE/mbapi2020 and covered by the corresponding MIT attribution (`LICENSE.mbapi2020`). No Home Assistant source is required by the plugin.
