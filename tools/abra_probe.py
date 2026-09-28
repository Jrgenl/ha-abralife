#!/usr/bin/env python3
"""Log in to Abralife and dump the GraphQL schema and raw device data.

Run this on your own PC to find the right queries for the integration:

    pip install aiohttp pycognito
    python tools/abra_probe.py --user you@example.com \
        --user-pool-id eu-west-1_XXXX --client-id XXXX \
        --api-url https://XXXX.appsync-api.eu-west-1.amazonaws.com/graphql

Writes abra_schema.json and abra_devices.json. The password is asked for
interactively and is not saved. Check the files before sharing them.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
import types
from dataclasses import asdict
from pathlib import Path

# Import api.py without importing Home Assistant.
_PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "abralife"
_pkg = types.ModuleType("abralife")
_pkg.__path__ = [str(_PKG_DIR)]
sys.modules["abralife"] = _pkg

import aiohttp  # noqa: E402

from abralife.api import AbraClient, AbraError  # noqa: E402
from abralife.const import (  # noqa: E402
    DEFAULT_API_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_REGION,
    DEFAULT_USER_POOL_ID,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", required=True)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--user-pool-id", default=DEFAULT_USER_POOL_ID)
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()
    for name in ("user_pool_id", "client_id", "api_url"):
        if not getattr(args, name):
            parser.error(f"--{name.replace('_', '-')} is required")

    password = getpass.getpass("Abralife password: ")
    async with aiohttp.ClientSession() as session:
        client = AbraClient(
            session, region=args.region, user_pool_id=args.user_pool_id,
            client_id=args.client_id, api_url=args.api_url,
        )
        try:
            await client.login(args.user, password)
            print("Login OK")
            try:
                Path("abra_schema.json").write_text(json.dumps(await client.introspect(), indent=2))
                print("Wrote abra_schema.json")
            except AbraError as err:
                print(f"Introspection failed ({err}); copy the schema from developer.abralife.com instead")
            homes = await client.get_homes()
            print("Homes:", [(h.id, h.name) for h in homes])
            dump = {h.id: [asdict(d) for d in (await client.get_devices(h.id)).values()] for h in homes}
            Path("abra_devices.json").write_text(json.dumps(dump, indent=2, default=str))
            print("Wrote abra_devices.json")
        except AbraError as err:
            print(f"Error: {type(err).__name__}: {err}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
