"""Autonomous Rally: ambiente de aprendizaje por refuerzo (Gymnasium)."""

from gymnasium.envs.registration import register

from rally.env import AutonomousRallyEnv, RallyConfig

register(id="AutonomousRally-v0", entry_point="rally.env:AutonomousRallyEnv")

__all__ = ["AutonomousRallyEnv", "RallyConfig"]
