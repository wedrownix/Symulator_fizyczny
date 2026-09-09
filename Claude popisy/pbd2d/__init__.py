"""
pbd2d -- silnik XPBD dla brył sztywnych 2D.

WARSTWY (zależności idą tylko w dół, nigdy w górę):

    vector2.py   algebra wektorowa            <- nie zależy od niczego
    config.py    parametry solvera
    xpbd.py      dwa wzory korekcyjne         <- vector2
    bodies.py    bryły i kształty             <- vector2, config
    joints.py    złącza                       <- bodies, xpbd
    world.py     SOLVER (krok czasowy)        <- bodies, joints, config
    builder.py   FABRYKA scen                 <- world, bodies, joints
    analyzer.py  pomiary i wykresy            <- world, bodies
    renderer.py  rysowanie (jedyny z pygame)  <- world, bodies, joints

Renderer nie jest importowany tutaj automatycznie, żeby dało się używać
silnika bez pygame (np. w testach albo przy liczeniu wsadowym).
"""

from .vector2 import Vec2, normalizeAngle, clamp
from .config import SolverConfig, WorldConfig
from .xpbd import applyLinearCorrection, applyAngularCorrection
from .bodies import Body, Beam, Disk, PointMass, CompositeBeam
from .joints import (Joint, RopeJoint, RevoluteJoint, FixedJoint,
                     SpringJoint, MotorJoint, PrismaticJoint)
from .world import World
from .builder import SceneBuilder
from .analyzer import Analyzer, Sample, Event

__all__ = [
    "Vec2", "normalizeAngle", "clamp",
    "SolverConfig", "WorldConfig",
    "applyLinearCorrection", "applyAngularCorrection",
    "Body", "Beam", "Disk", "PointMass", "CompositeBeam",
    "Joint", "RopeJoint", "RevoluteJoint", "FixedJoint",
    "SpringJoint", "MotorJoint", "PrismaticJoint",
    "World", "SceneBuilder", "Analyzer", "Sample", "Event",
]
