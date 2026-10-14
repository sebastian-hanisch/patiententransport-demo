"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen; Permalink-Begrenzung."""

import ptd_constants as C
import ptd_evaluation as ev
import ptd_presets as P


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_inside_the_slider_bounds():
    for name, p in C.PRESETS.items():
        assert C.RATE_MIN <= p["rate"] <= C.RATE_MAX, name
        assert C.PORTERS_MIN <= p["porters"] <= C.PORTERS_MAX, name
        assert C.QUAL_MIN <= p["qual"] <= C.QUAL_MAX, name
        assert C.BATCH_MIN <= p["batch"] <= C.BATCH_MAX, name
        assert p["breaks"] in C.BREAKS_OPTIONS and 0 <= p["seed"] <= C.SEED_MAX, name


def test_default_preset_equals_the_default_settings():
    assert ev.Settings(**C.PRESETS["Standardfall (Voreinstellung)"]) == ev.Settings()


def test_setting_specs_cover_every_preset_key():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)


def test_permalink_values_are_clamped_and_choices_snapped():
    spec = P.SETTING_SPECS["rate_slider"]
    assert P.clamp_setting(spec, "999") == C.RATE_MAX and P.clamp_setting(spec, "-4") == C.RATE_MIN
    assert P.clamp_setting(spec, "abc") is None
    breaks = P.SETTING_SPECS["breaks_radio"]
    assert P.clamp_setting(breaks, "ohne Pausen") == "ohne Pausen" and P.clamp_setting(breaks, "irgendwas") is None


def test_the_standard_day_has_enough_emergencies_to_say_something():
    assert ev.analyse(ev.Settings()).stats["fifo"].classes[0].n >= 6
