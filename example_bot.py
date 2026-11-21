"""Mech Royale entrypoint: a survival-first bot with campus navigation."""
import mechfight as mf
from strategy import SurvivalPolicy


class Bot(SurvivalPolicy):
    name = "Evans-Survival-v2"


mf.run(Bot)
