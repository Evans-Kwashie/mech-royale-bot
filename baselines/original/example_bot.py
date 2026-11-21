"""Importable c029917 baseline; unlike the production entrypoint, no main call."""
import strategy as strategy_module
from strategy import SurvivalPolicy


USES_NATIVE_ARENA = True


class Bot(SurvivalPolicy):
    name = "Evans-Survival-v2"
    _shared_arena = None

    def __init__(self, hello):
        if Bot._shared_arena is None:
            super().__init__(hello)
            Bot._shared_arena = self.arena
        else:
            original = strategy_module.Arena
            strategy_module.Arena = lambda _path: Bot._shared_arena
            try:
                super().__init__(hello)
            finally:
                strategy_module.Arena = original


if __name__ == "__main__":
    import mechfight as mf

    mf.run(Bot)
