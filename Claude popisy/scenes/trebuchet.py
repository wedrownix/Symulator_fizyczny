"""
scenes/trebuchet.py -- scena trebusza zbudowana przez SceneBuilder.

Scena jest osobnym plikiem, bo zmienia się z zupełnie innego powodu niż
silnik: gdy chcę inną maszynę, nie dotykam ani solvera, ani buildera.

KONSTRUKCJA
    belka pozioma (density = 0, nieruchoma)
      + dwie belki spięte SPAWEM -> trójkąt (rama A)
      + w wierzchołku ZAWIAS -> ramię miotające, oś w proporcji 1:3
      + krótki koniec: LINA Z OGNIW -> przeciwwaga 100 kg     [tag: "przeciwwaga"]
      + długi koniec:  dłuższa LINA Z OGNIW -> pocisk 1 kg    [tag: "proca"]

ETYKIETY (tag)
    Każda lina dostaje etykietę, po której można ją zwolnić w trakcie
    symulacji: world.release("proca"). To jest ten "spust" - pocisk odlatuje,
    a lina zostaje na ramieniu.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

from pbd2d import Vec2, World, SceneBuilder


@dataclass
class TrebuchetParams:
    """Wszystkie parametry maszyny w jednym miejscu - gotowe pod optymalizację.

    Żeby zbadać wpływ dowolnego parametru na zasięg, wystarczy pętla po
    wartościach tego pola; nic więcej w kodzie się nie zmienia."""
    baseWidth: float = 1.6            # belka podstawy
    baseHeight: float = 0.10
    apexHeight: float = 1.8           # wysokość wierzchołka trójkąta
    legThickness: float = 0.08
    legDensity: float = 25.0

    armLength: float = 2.0            # długość ramienia
    armPivot: float = 0.25            # oś w 1/4 długości -> proporcja 1:3
    armTilt: float = 1.1              # początkowe nachylenie [rad]
    armThickness: float = 0.07
    armDensity: float = 12.0

    counterMass: float = 100.0        # przeciwwaga
    counterRope: float = 0.30         # długość krótkiej liny
    counterNodes: int = 3

    projectileMass: float = 1.0       # pocisk
    projectileRadius: float = 0.07
    slingLength: float = 1.8          # długość procy
    slingNodes: int = 5

    releaseAngle: float = math.pi - 1.10   # kąt ramienia dla auto-zwolnienia


def build(world: World, p: TrebuchetParams = None) -> SceneBuilder:
    """Buduje trebusz w podanym świecie i zwraca buildera.

    Dostęp do części po nazwie: builder["ramie"], builder["pocisk"] itd."""
    p = p or TrebuchetParams()
    world.clear()
    b = SceneBuilder(world)

    # --- 1. podstawa: density = 0 -> masa 0 -> element nieruchomy
    base = b.beam("podstawa", 0.0, p.baseHeight / 2,
                  p.baseWidth, p.baseHeight, density=0.0,
                  color=(120, 122, 132))

    # --- 2. rama A: dwie belki przyspawane do podstawy i do siebie
    apex = Vec2(0.0, p.apexHeight)
    legs = []
    for i, sign in enumerate((-1.0, 1.0)):
        foot = base.end(sign)
        leg = b.beamBetween(f"noga{i}", foot, apex, p.legThickness,
                            p.legDensity, color=(176, 138, 84))
        b.fixed(base, leg, foot)              # SPAW do podstawy
        legs.append(leg)
    b.fixed(legs[0], legs[1], apex)           # SPAW w wierzchołku

    # --- 3. ramię miotające na ZAWIASIE w wierzchołku
    # oś leży w localAt(-0.5) czyli w 1/4 długości od lewego końca, więc
    # środek masy jest przesunięty o +armLength/4 względem osi
    armAngle = math.pi + p.armTilt            # długi koniec skierowany w dół
    armCenter = apex.clone().add(
        Vec2(p.armPivot * p.armLength, 0.0).rotate(armAngle))
    arm = b.beam("ramie", armCenter.x, armCenter.y, p.armLength,
                 p.armThickness, density=p.armDensity, angle=armAngle,
                 color=(232, 202, 122))
    b.revolute(legs[0], arm, apex, tag="os")

    # --- 4. przeciwwaga na krótkiej linie z ogniw
    shortTip = arm.end(-1.0)
    cwPos = shortTip.clone().add(Vec2(0.0, -p.counterRope))
    counterweight = b.pointMass("przeciwwaga", cwPos.x, cwPos.y,
                                p.counterMass, 0.14, color=(205, 70, 70))
    b.ropeChain(arm, shortTip, counterweight, cwPos,
                numNodes=p.counterNodes, nodeMass=p.counterMass / 50.0,
                tag="przeciwwaga", namePrefix="cw")

    # --- 5. pocisk na procy (dłuższa lina z ogniw), leży na ziemi
    longTip = arm.end(1.0)
    dy = longTip.y - p.projectileRadius
    dx = math.sqrt(max(p.slingLength ** 2 - dy * dy, 0.04))
    projPos = Vec2(longTip.x - dx, p.projectileRadius)
    projectile = b.pointMass("pocisk", projPos.x, projPos.y,
                             p.projectileMass, p.projectileRadius,
                             color=(90, 200, 255))
    b.ropeChain(arm, longTip, projectile, projPos,
                numNodes=p.slingNodes,
                nodeMass=max(p.projectileMass / 20.0, 0.05),
                length=p.slingLength, tag="proca", namePrefix="proca")

    return b
