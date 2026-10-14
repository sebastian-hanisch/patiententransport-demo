"""Permalink (Begrenzen/Einrasten), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import ptd_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    lo: float | None = None
    hi: float | None = None
    choices: tuple | None = None


SETTING_SPECS = {
    "rate_slider": SettingSpec("rate", int, C.DEFAULT_RATE, C.RATE_MIN, C.RATE_MAX),
    "porters_slider": SettingSpec("porters", int, C.DEFAULT_PORTERS, C.PORTERS_MIN, C.PORTERS_MAX),
    "qual_slider": SettingSpec("qual", int, C.DEFAULT_QUAL, C.QUAL_MIN, C.QUAL_MAX),
    "batch_slider": SettingSpec("batch", int, C.DEFAULT_BATCH, C.BATCH_MIN, C.BATCH_MAX),
    "breaks_radio": SettingSpec("breaks", str, C.DEFAULT_BREAKS, choices=C.BREAKS_OPTIONS),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
}
PRESET_KEYS = {"rate": "rate_slider", "porters": "porters_slider", "qual": "qual_slider", "batch": "batch_slider",
               "breaks": "breaks_radio", "seed": "seed_input"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def clamp_setting(spec: SettingSpec, raw):
    """Rohwert aus der Adresszeile -> gültiger Wert (auf die Grenzen begrenzt, Auswahl nur aus den erlaubten Werten); None, wenn unbrauchbar."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if spec.choices is not None:
        return value if value in spec.choices else None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    return value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = clamp_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
