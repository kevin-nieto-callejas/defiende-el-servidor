"""Autonomous Rally: ambiente de aprendizaje por refuerzo (Gymnasium), en carro o en moto MotoGP."""

from gymnasium.envs.registration import register

from rally.env import AutonomousRallyEnv, RallyConfig
from rally.moto import MotoConfig, MotoGPEnv

register(id="AutonomousRally-v0", entry_point="rally.env:AutonomousRallyEnv")
register(id="AutonomousRallyMoto-v0", entry_point="rally.moto:MotoGPEnv")

__all__ = ["AutonomousRallyEnv", "RallyConfig", "MotoGPEnv", "MotoConfig"]
