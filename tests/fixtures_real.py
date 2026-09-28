"""Anonymised copy of a real Waterguard+ installation (Linkbox+ WiFi, valve,
sensor tape and two WaterSensor+), as returned for queries.HOMES_QUERY."""

HUB = "hub-1"


def _attrs(*items: dict) -> list[dict]:
    return list(items)


REAL_HOME = {
    "id": "home-1",
    "homeInfo": {"nickname": "Hjemme"},
    "hubs": [
        {
            "id": HUB,
            "name": "Linkbox+ WiFi",
            "serialNumber": "x",
            "firmwareVersion": "2.376.4",
            "productType": "HUB_WIFI",
            "area": None,
            "waterGuard": {"mode": "RESTORED", "showLevel1Warning": False, "showLevel2Warning": False},
            "traits": [
                {"traitType": "POWER", "commands": [], "attributes": _attrs(
                    {"__typename": "TraitAttributeBatteryVoltage"},
                    {"__typename": "TraitAttributeCurrentPowerSourceLevel", "currentPowerSourceLevel": 0},
                )},
                {"traitType": "STATUS", "commands": [], "attributes": _attrs(
                    {"__typename": "TraitAttributeFault", "fault": [
                        {"code": "ZBPM001", "name": "fault/disconnect", "description": "battery absent"}]},
                    {"__typename": "TraitAttributeOta"},
                )},
                {"traitType": "CONNECTION", "commands": [], "attributes": _attrs(
                    {"__typename": "TraitAttributeIsConnected", "isConnected": True, "reportedAt": "2026-09-16T07:11:27Z"},
                )},
            ],
            "devices": [
                {
                    "id": "sensor-kitchen",
                    "deviceType": "WATER_LEAK_DETECTOR",
                    "name": "Waterguard+ Water Sensor",
                    "serialNumber": "x",
                    "firmwareVersion": None,
                    "area": {"areaName": "Kitchen"},
                    "traits": [
                        {"traitType": "WARNING_DEVICE", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeAlarm", "alarm": "NO_ALARM", "snoozed": False})},
                        {"traitType": "POWER", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeCurrentPowerSource"},
                            {"__typename": "TraitAttributeCurrentPowerSourceLevel", "currentPowerSourceLevel": 62},
                            {"__typename": "TraitAttributeLowBatteryWarning", "lowBatteryWarning": False})},
                        {"traitType": "SENSOR", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeHumidity", "humidity": 29.0},
                            {"__typename": "TraitAttributeTemperature", "temperature": 27.0})},
                        {"traitType": "CONNECTION", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeIsConnected", "isConnected": False,
                             "reportedAt": "2026-04-03T15:57:54Z"},
                            {"__typename": "TraitAttributeLinkQuality"})},
                    ],
                },
                {
                    "id": f"{HUB}valveMonitor",
                    "deviceType": "WATER_VALVE",
                    "name": "Waterguard+ Valve",
                    "serialNumber": "x",
                    "firmwareVersion": None,
                    "area": None,
                    "traits": [
                        {"traitType": "STATUS", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeFault", "fault": []})},
                        {"traitType": "CONNECTION", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeIsConnected", "isConnected": True,
                             "reportedAt": "2026-05-06T02:10:57Z"})},
                        {"traitType": "OPEN_CLOSE", "commands": ["OPEN_PERCENT"], "attributes": _attrs(
                            {"__typename": "TraitAttributeOpenPercent"})},
                        {"traitType": "INFO", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeValveInfo"}, {"__typename": "TraitAttributeValveState"})},
                    ],
                },
                {
                    "id": f"{HUB}waterMonitor",
                    "deviceType": "WATER_SENSOR_TAPE",
                    "name": "Linkbox+ Sensortape",
                    "serialNumber": "x",
                    "firmwareVersion": None,
                    "area": None,
                    "traits": [
                        {"traitType": "WARNING_DEVICE", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeAlarm", "alarm": "NO_ALARM", "snoozed": False})},
                        {"traitType": "WATER", "commands": [], "attributes": _attrs(
                            {"__typename": "TraitAttributeWaterDetectorCableConnected"})},
                    ],
                },
            ],
        }
    ],
}


# Response to queries.EXTRAS_QUERY for the same home
REAL_EXTRAS = {
    "homes": [{"id": "home-1", "hubs": [{"devices": [
        {"id": f"{HUB}valveMonitor", "traits": [{"attributes": [
            {"__typename": "TraitAttributeOpenPercent", "openPercent": 100.0}]}]},
        {"id": "sensor-kitchen", "traits": [{"attributes": [
            {"__typename": "TraitAttributeCurrentPowerSource", "currentPowerSource": "BATTERY"},
            {"__typename": "TraitAttributeLinkQuality"}]}]},
    ]}]}]
}
