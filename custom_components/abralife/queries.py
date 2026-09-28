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


# Diagnostics only: every trait attribute type in the schema (except network
# credentials and location), so a diagnostics download shows exactly what
# Abra reports for a device. Not used for polling.
_ALL_ATTRIBUTES = """
  attributes {
        __typename
        ... on TraitAttributeAvailableArmLevels { name availableArmLevels { id description } }
        ... on TraitAttributeIsArmed { name isArmed }
        ... on TraitAttributeArmLevel { name armLevel }
        ... on TraitAttributeDisarmDefaultTimeout { name disarmDefaultTimeout }
        ... on TraitAttributeIsConnected { name isConnected reportedAt }
        ... on TraitAttributeHeartbeatInterval { name heartbeatInterval }
        ... on TraitAttributeHeartbeatsThreshold { name heartbeatsThreshold }
        ... on TraitAttributeGatewayConnected { name ethernetConnected wifiConnected cellularConnected }
        ... on TraitAttributeWifiConfigured { name wifiConfigured }
        ... on TraitAttributeCellularOperator { name cellularOperator }
        ... on TraitAttributeBrightness { name brightness }
        ... on TraitAttributeColor { name hue saturation }
        ... on TraitAttributeIsOn { name isOn }
        ... on TraitAttributeOpenPercent { name openPercent }
        ... on TraitAttributeCurrentPowerSourceLevel { name currentPowerSourceLevel }
        ... on TraitAttributeLowBatteryWarning { name lowBatteryWarning }
        ... on TraitAttributeCurrentPowerSource { name currentPowerSource }
        ... on TraitAttributeStatusCharging { name statusCharging }
        ... on TraitAttributeCurrentPowerMode { name currentPowerMode }
        ... on TraitAttributeAvailablePowerSources { name availablePowerSources }
        ... on TraitAttributeBatteryVoltage { name batteryVoltage }
        ... on TraitAttributeMainsVoltage { name mainsVoltage }
        ... on TraitAttributeRunningPowerConsumption { name runningPowerConsumption }
        ... on TraitAttributePriority { name priority }
        ... on TraitAttributeAirQuality { name airQuality }
        ... on TraitAttributeCo2 { name co2 }
        ... on TraitAttributeHumidity { name humidity humidityIndicator }
        ... on TraitAttributeTemperature { name temperature }
        ... on TraitAttributeVoc { name voc }
        ... on TraitAttributeIsUnlocked { name isUnlocked }
        ... on TraitAttributeChildLock { name childLock }
        ... on TraitAttributeFault { name fault { id name code description consumer guiPriority } }
        ... on TraitAttributeTemperatureSetpoint { name temperatureSetpoint minSetpoint maxSetpoint }
        ... on TraitAttributeTemperatureSetpointPercentage { name temperatureSetpointPercentage minSetpoint maxSetpoint }
        ... on TraitAttributeAvailableClimateModes { name availableClimateModes }
        ... on TraitAttributeClimateMode { name climateMode }
        ... on TraitAttributeMaximumFloorTemperature { name maximumFloorTemperature }
        ... on TraitAttributeFrostGuard { name frostGuard }
        ... on TraitAttributeNightSwitch { name nightSwitch }
        ... on TraitAttributeRegulatorMode { name regulatorMode }
        ... on TraitAttributeHeatingElementActive { name heatingElementActive }
        ... on TraitAttributeAlarmSound { name alarmSound }
        ... on TraitAttributeAlarm { name alarm snoozed }
        ... on TraitAttributeWaterDetectorCableConnected { name waterDetectorCableConnected }
        ... on TraitAttributeWaterValvesConnected { name waterValvesConnected }
        ... on TraitAttributeBracket { name bracket }
        ... on TraitAttributeDisabled { name disabled }
        ... on TraitAttributeMotionDetected { name lastMotionDetectedAt }
        ... on TraitAttributeValveInfo { name valveType typeOfValve numValves }
        ... on TraitAttributeElectricVehicleCharger { name status chargingStartedAt chargingFinishedAt chargingSessionCost kwhCharged currency }
        ... on TraitAttributeEvChargingSpeed { name evCurrentAmperage evMinAmperage evMaxAmperage }
        ... on TraitAttributeTestMode { name isOn lastTriggeredAt }
        ... on TraitAttributePing { name ping }
        ... on TraitAttributeBasicInfo { name firmwareVersion model }
  }
"""

DIAGNOSTICS_QUERY = f"""
query AbraDiagnostics {{
  homes {{
    id
    hubs {{
      id
      name
      hubType
      productType
      firmwareVersion
      waterGuard {{ mode wasWaterSensorTapePreviouslyConnected showLevel1Warning showLevel2Warning }}
      traits {{ traitType commands {_ALL_ATTRIBUTES} }}
      devices {{
        id
        deviceType
        name
        firmwareVersion
        manufacturer {{ name }}
        traits {{ traitType commands {_ALL_ATTRIBUTES} }}
      }}
    }}
  }}
}}
"""
