"""GraphQL documents used against the Abralife API.

Based on the official schema and the Abra Connect SDK 0.2.0 published on
https://developer.abralife.com/ (``/schema.graphql``).
"""

from __future__ import annotations

_DEVICE_ATTRIBUTES = """
  attributes {
    __typename
    ... on TraitAttributeIsConnected { isConnected reportedAt }
    ... on TraitAttributeIsUnlocked { isUnlocked }
    ... on TraitAttributeAlarm { alarm snoozed }
    ... on TraitAttributeTemperature { temperature }
    ... on TraitAttributeHumidity { humidity }
    ... on TraitAttributeCurrentPowerSourceLevel { currentPowerSourceLevel }
    ... on TraitAttributeLowBatteryWarning { lowBatteryWarning }
    ... on TraitAttributeWaterValvesConnected { waterValvesConnected }
    ... on TraitAttributeFault { fault { code name description } }
  }
"""

HOMES_QUERY = f"""
query AbraHomes {{
  homes {{
    id
    homeInfo {{ nickname }}
    hubs {{
      id
      name
      serialNumber
      firmwareVersion
      productType
      area {{ areaName }}
      waterGuard {{ mode showLevel1Warning showLevel2Warning }}
      traits {{ traitType commands {_DEVICE_ATTRIBUTES} }}
      devices {{
        id
        deviceType
        name
        serialNumber
        firmwareVersion
        area {{ areaName }}
        traits {{ traitType commands {_DEVICE_ATTRIBUTES} }}
      }}
    }}
  }}
}}
"""

HOME_IDS_QUERY = """
query AbraHomeIds {
  homes {
    id
    homeInfo { nickname }
  }
}
"""

ALARMS_QUERY = """
query AbraAlarms($homeId: ID!) {
  alarms(homeId: $homeId) {
    alarms {
      __typename
      ... on WaterAlarm { id state triggeredAt }
      ... on FireAlarm { id state triggeredAt }
      ... on SecurityAlarm { id state triggeredAt }
    }
  }
}
"""

# Abra models the water valve as "unlocked" = open (see SDK setValveOpen).
SET_VALVE_MUTATION = """
mutation AbraSetValve($deviceId: ID!, $open: Boolean!) {
  deviceSetUnlocked(deviceId: $deviceId, isUnlocked: $open, commandSource: CUSTOMER) {
    command { commandState commandType }
    errors {
      __typename
      ... on DeviceDoesNotExistError { message }
      ... on TraitNotSupportedForDeviceError { message }
      ... on TraitUpdateFailedError { message }
    }
  }
}
"""

# Resolving a water alarm never opens the valve.
ALARM_RESOLVE_MUTATION = """
mutation AbraAlarmResolve($alarmId: ID!) {
  alarmResolve(alarmId: $alarmId) {
    alarmId
    errors {
      __typename
      ... on AlarmDoesNotExistError { message }
    }
  }
}
"""
