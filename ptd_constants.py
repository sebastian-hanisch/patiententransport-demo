"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets.

Alle Eingangszahlen sind Annahmen eines synthetischen Hauses, keine Messung aus einem echten Betrieb (README, "Ehrliche Grenzen").
"""

# --- Regler ------------------------------------------------------------------------------------------------------------------------------
RATE_MIN, RATE_MAX, DEFAULT_RATE = 8, 36, 20          # neue Aufträge je Stunde im Mittel, ohne Rückholungen
PORTERS_MIN, PORTERS_MAX, DEFAULT_PORTERS = 4, 14, 8
QUAL_MIN, QUAL_MAX, DEFAULT_QUAL = 40, 100, 85        # Prozent der Träger mit Bett-Qualifikation
BATCH_MIN, BATCH_MAX, DEFAULT_BATCH = 2, 15, 5        # Länge des Sammelfensters in Minuten
SEED_MAX, DEFAULT_SEED = 999999, 29
BREAKS_OPTIONS = ("mit Pausen", "ohne Pausen")
DEFAULT_BREAKS = "mit Pausen"

# --- Tag und Betrieb ---------------------------------------------------------------------------------------------------------------------
DAY_MINUTES = 720                    # Meldefenster 06:00 bis 18:00
DAY_START_HOUR = 6
SIM_LIMIT = 1800                     # harte Obergrenze der Simulationszeit (Minuten); der Tag läuft bis alle Aufträge erledigt sind
HANDOVER = 2                         # Minuten Übergabe je Ende einer Fahrt
BREAK_START, BREAK_LEN, BREAK_STAGGER, BREAK_SLOTS = 330, 30, 20, 4   # ab 11:30, 30 min, gestaffelt in vier Gruppen
BASE_RATE = 34.0                     # Hinfahrten je Stunde bei Dichte 1,0 (Referenz für die Umrechnung der Reglerwerte)
PROFILE = (0.5, 1.3, 1.6, 1.4, 1.1, 0.9, 1.0, 1.2, 1.3, 1.1, 0.8, 0.6)   # relative Dichte je Stunde 06 bis 17 Uhr (OP-Beginn, Entlassungen)
PEAK_PROFILE_LEVEL = 1.4             # konstante Spitzendichte der kleinen Instanzen für die Hindsight-Schranke

# --- Klassen, Soll, Gewichte ---------------------------------------------------------------------------------------------------------------
CLASS_NAMES = ("Notfall", "dringend", "Routine")
SOLL = (10, 20, 40)                  # Minuten von der Meldung bis zur Ankunft am Abholort
CLASS_WEIGHT = (8, 3, 1)             # Gewicht je Klasse in der gewichteten Wartezeit (Zielgröße der Schranke, Alterungsgewicht der Zuordnung)
KINDS = ("bett", "rollstuhl", "gehend")
KIND_LABEL = {"bett": "Bett", "rollstuhl": "Rollstuhl", "gehend": "gehend"}
SPEED = {"leer": 85.0, "bett": 60.0, "rollstuhl": 75.0, "gehend": 50.0}   # Meter je Minute
LIFT_BASE, LIFT_PER_FLOOR, BUILDING_CHANGE = 1.2, 0.3, 1.5

# --- Regeln ------------------------------------------------------------------------------------------------------------------------------
RULES = ("fifo", "nahe", "prio", "frist", "batch", "voraus")
RULE_NAME = {
    "fifo": "FIFO",
    "nahe": "Nächster Auftrag",
    "prio": "Priorität",
    "frist": "Frist (EDD)",
    "batch": "Sammelfenster",
    "voraus": "Vorausschau",
}
RULE_TEXT = {
    "fifo": "Ältester Auftrag zuerst, der nächste freie Träger fährt.",
    "nahe": "Immer das Paar aus freiem Träger und wartendem Auftrag mit der kürzesten Anfahrt.",
    "prio": "Notfall vor dringend vor Routine, innerhalb der Klasse der älteste zuerst; der nächste freie Träger fährt.",
    "frist": "Früheste Soll-Frist zuerst (Meldung plus Soll der Klasse); der nächste freie Träger fährt.",
    "batch": "Notfälle sofort; alle anderen werden nur im Takt des Sammelfensters optimal zugeordnet.",
    "voraus": "Jede Minute optimal zugeordnet, bald freie Träger (innerhalb von 8 min) zählen mit; Notfälle sofort.",
}
LOOKAHEAD_MIN = 8                    # Vorausschau: so weit in die Zukunft zählen bald freie Träger mit

# --- Sweeps und Schranke ------------------------------------------------------------------------------------------------------------------
SWEEP_SEEDS = tuple(range(100000, 100008))      # feste Tage für alle Sweeps: nie ein einzelner Seed als Befund
RATE_SWEEP = (12, 16, 20, 24, 28, 32)
HINDSIGHT_SEEDS = tuple(range(2000, 2012))
HINDSIGHT_PORTERS = 3
HINDSIGHT_LEVELS = {                 # Name: (Fenster in Minuten, Dichte-Faktor m)
    "locker (60 min, m 0,15)": (60, 0.15),
    "mittel (60 min, m 0,225)": (60, 0.225),
    "dicht (40 min, m 0,30)": (40, 0.30),
}
DEFAULT_HINDSIGHT_LEVEL = "locker (60 min, m 0,15)"
HINDSIGHT_TIME_LIMIT = 20.0
HINDSIGHT_MAX_JOBS = 32

# --- Farben ------------------------------------------------------------------------------------------------------------------------------
COLOR_CLASS = ("#B5332A", "#D98A1F", "#2F6B65")        # Notfall, dringend, Routine
COLOR_RULE = {
    "fifo": "#7A7A7A", "nahe": "#4C78A8", "prio": "#B5332A", "frist": "#9467BD", "batch": "#D98A1F", "voraus": "#2F6B65",
}
COLOR_SOLL = "rgba(60,60,60,0.55)"

# --- Presets -----------------------------------------------------------------------------------------------------------------------------
PRESETS = {
    "Standardfall (Voreinstellung)": {"rate": DEFAULT_RATE, "porters": DEFAULT_PORTERS, "qual": DEFAULT_QUAL, "batch": DEFAULT_BATCH,
                                      "breaks": DEFAULT_BREAKS, "seed": DEFAULT_SEED},
    "Ruhiger Tag": {"rate": 12, "porters": DEFAULT_PORTERS, "qual": DEFAULT_QUAL, "batch": DEFAULT_BATCH,
                    "breaks": DEFAULT_BREAKS, "seed": DEFAULT_SEED},
    "Dichter Tag": {"rate": 26, "porters": DEFAULT_PORTERS, "qual": DEFAULT_QUAL, "batch": DEFAULT_BATCH,
                    "breaks": DEFAULT_BREAKS, "seed": DEFAULT_SEED},
    "Zu wenig Träger": {"rate": DEFAULT_RATE, "porters": 5, "qual": DEFAULT_QUAL, "batch": DEFAULT_BATCH,
                        "breaks": DEFAULT_BREAKS, "seed": DEFAULT_SEED},
    "Wenige Bett-Qualifizierte": {"rate": DEFAULT_RATE, "porters": DEFAULT_PORTERS, "qual": 40, "batch": DEFAULT_BATCH,
                                  "breaks": DEFAULT_BREAKS, "seed": DEFAULT_SEED},
}
PRESET_HELP = {
    "Standardfall (Voreinstellung)": "8 Träger, 20 neue Aufträge je Stunde im Mittel (rund 85 % Auslastung): hier laufen die Regeln auseinander.",
    "Ruhiger Tag": "12 neue Aufträge je Stunde: weit unter der Kapazität, die Regeln unterscheiden sich kaum.",
    "Dichter Tag": "26 neue Aufträge je Stunde: an der Kapazitätsgrenze, keine Regel hält alle Klassen im Soll.",
    "Zu wenig Träger": "Nur 5 Träger bei Standarddichte: die Last liegt über der Kapazität.",
    "Wenige Bett-Qualifizierte": "Nur 40 % der Träger dürfen Betten fahren: Bett-Aufträge warten auf wenige Hände.",
}
