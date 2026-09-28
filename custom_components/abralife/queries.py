"""GraphQL documents used against the Abralife API.

All GraphQL lives in this one file so it can be aligned with the official
schema on https://developer.abralife.com/apis/schema without touching the rest
of the integration. Run ``tools/abra_probe.py`` to dump the live schema.

The parser in ``api.py`` is deliberately tolerant about field names, so small
naming differences only need to be fixed here.
"""

from __future__ import annotations

HOMES_QUERY = """
query AbraHomes {
  homes {
    id
    name
  }
}
"""

DEVICES_QUERY = """
query AbraDevices($homeId: ID!) {
  home(id: $homeId) {
    id
    name
    devices {
      id
      name
      type
      model
      online
      room { name }
      state
    }
  }
}
"""

SET_VALVE_MUTATION = """
mutation AbraSetValve($deviceId: ID!, $open: Boolean!) {
  setValveState(deviceId: $deviceId, open: $open) {
    id
    state
  }
}
"""

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      fields(includeDeprecated: true) {
        name
        args { name type { kind name ofType { kind name ofType { kind name } } } }
        type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
      }
      inputFields { name type { kind name ofType { kind name ofType { kind name } } } }
      enumValues(includeDeprecated: true) { name }
    }
  }
}
"""
