# Abralife (Waterguard+) for Home Assistant

Uoffisiell Home Assistant-integrasjon for **Waterguard+** vannlekkasjesikring via
Abralife-skyen. Installeres med HACS og settes opp med en veiviser: du skriver
bare inn e-post og passord fra Abralife-appen.

> Status: **beta**. Integrasjonen bruker Abras offisielle GraphQL-API
> ([developer.abralife.com](https://developer.abralife.com/)). Spørringene i
> `queries.py` må verifiseres mot det offisielle skjemaet før 1.0.

## Hva du får

| Enhet | Entitet i Home Assistant |
|---|---|
| Linkbox+ / vannventil | `valve` – vis status og steng vannet (åpning kan slås på, se under) |
| WaterSensor+ / sensortape | `binary_sensor` (fukt/lekkasje) |
| WaterSensor+ | `sensor` for temperatur, luftfuktighet og batteri |
| Alle enheter | `binary_sensor` for tilkobling (diagnostikk) |

**Sikkerhet:**
- Passordet ditt lagres aldri. Det brukes én gang til å hente en
  innloggingsnøkkel (refresh token) fra Abra. Hvis nøkkelen utløper, ber Home
  Assistant deg logge inn på nytt.
- Å **stenge** vannet er alltid lov. Å **åpne** vannet fra Home Assistant er
  slått av som standard, i tråd med Abras anbefaling om at gjenåpning skal være
  en bevisst handling etter at lekkasjen er utbedret. Du kan slå det på under
  *Innstillinger → Enheter og tjenester → Abralife → Konfigurer*.

## Installasjon (HACS)

1. Åpne HACS → ⋮ → **Egendefinerte repositorier**.
2. Lim inn `https://github.com/jrgenl/ha-abralife`, velg type **Integrasjon**, og klikk *Legg til*.
3. Søk opp **Abralife (Waterguard+)** i HACS og klikk *Last ned*.
4. Start Home Assistant på nytt.
5. Gå til **Innstillinger → Enheter og tjenester → Legg til integrasjon** og søk etter **Abralife**.
6. Skriv inn e-post og passord fra Abralife-appen. Har du flere hjem, velger du hvilket.

[![Åpne i HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jrgenl&repository=ha-abralife&category=integration)

### Manuell installasjon
Kopier `custom_components/abralife` til `config/custom_components/` og start på nytt.

## Eksempel: steng vannet og varsle ved lekkasje

Waterguard+ stenger selv vannet ved lekkasje. Dette er et ekstra lag, f.eks. for
å varsle hele husstanden:

```yaml
automation:
  - alias: "Vannlekkasje"
    triggers:
      - trigger: state
        entity_id:
          - binary_sensor.kjokken_lekkasje
        to: "on"
    actions:
      - action: valve.close_valve
        target:
          entity_id: valve.hovedkran
      - action: notify.notify
        data:
          title: "💧 Vannlekkasje!"
          message: "Lekkasje oppdaget på {{ trigger.to_state.name }}. Vannet er stengt."
```

## For utviklere / feilsøking

- All GraphQL ligger i `custom_components/abralife/queries.py`. Tilkoblingsverdier
  (region, Cognito user pool, client ID, AppSync-URL) ligger i `const.py`. Når de
  er fylt ut der, ser brukerne bare e-post og passord i veiviseren.
- `tools/abra_probe.py` logger inn fra egen PC og lagrer skjema og rådata for
  enhetene i `abra_schema.json` og `abra_devices.json`.
- Under *Enheter og tjenester → Abralife → ⋮ → Last ned diagnostikk* får du rådata
  fra enhetene (tokens og e-post er fjernet).
- Tester: `pip install pytest-homeassistant-custom-component pycognito && pytest`.

Ikke tilknyttet Abra AS eller Waterguard AS.
