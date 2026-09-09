"""
pbd2d/builder.py -- SceneBuilder: fabryka obiektów sceny.

WZORCE
    Fabryka (metody wytwórcze)  -- klient nie woła konstruktorów i nie musi
        pamiętać, że ciało trafia do world.bodies, a złącze do world.joints.
    Płynne API                  -- metody bez zwracanej wartości oddają self,
        więc scenę można budować łańcuchem wywołań.
    Rejestr nazw                -- każdy element dostaje nazwę, po której
        można się do niego odwołać ("maszt", "pocisk"), zamiast trzymać
        zmienne lokalne. Ułatwia potem podpięcie Analyzera i zwalnianie więzów.

DLACZEGO OSOBNA KLASA (SOLID: S)
    World zmienia się, gdy zmienia się algorytm symulacji.
    SceneBuilder zmienia się, gdy zmienia się wygoda budowania scen.
    To dwa niezależne powody, więc dwie klasy.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional

from .vector2 import Vec2
from .bodies import Body, Beam, Disk, PointMass, CompositeBeam
from .joints import (Joint, RopeJoint, RevoluteJoint, FixedJoint,
                     SpringJoint, MotorJoint, PrismaticJoint)
from .world import World


class SceneBuilder:
    """Buduje scenę "z klocków" i rejestruje wszystko w podanym świecie."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.named: Dict[str, Body] = {}      # rejestr nazw -> ciało

    # =====================================================================
    #  CIAŁA
    # =====================================================================
    def beam(self, name: str, x: float, y: float, width: float, height: float,
             density: float = 1.0, angle: float = 0.0, **kw) -> Beam:
        """Prostokąt o środku w (x, y). density = 0 -> element nieruchomy."""
        return self._register(Beam(Vec2(x, y), width, height, density, angle,
                                   name=name, **kw))

    def beamBetween(self, name: str, a: Vec2, b: Vec2, thickness: float,
                    density: float = 1.0, **kw) -> Beam:
        """Belka rozpięta między dwoma punktami.

        Konstruktor Beam chce środek, długość i kąt, a przy budowaniu
        kratownicy naturalnie zna się dwa końce - fabryka tłumaczy jedno
        na drugie."""
        d = Vec2().subtractVectors(b, a)
        mid = Vec2().addVectors(a, b).scale(0.5)
        return self._register(Beam(mid, d.length(), thickness, density,
                                   math.atan2(d.y, d.x), name=name, **kw))

    def disk(self, name: str, x: float, y: float, radius: float,
             density: float = 1.0, **kw) -> Disk:
        return self._register(Disk(Vec2(x, y), radius, density, name=name, **kw))

    def pointMass(self, name: str, x: float, y: float, mass: float,
                  radius: float = 0.05, **kw) -> PointMass:
        return self._register(PointMass(Vec2(x, y), mass, radius,
                                        name=name, **kw))

    def compositeBeam(self, name: str, x: float, y: float,
                      width: float, height: float, density: float,
                      extraMass: float, extraAt: float, angle: float = 0.0,
                      **kw) -> CompositeBeam:
        """Belka z doczepionym obciążnikiem jako JEDNA bryła (ręczne I)."""
        return self._register(CompositeBeam(Vec2(x, y), width, height, density,
                                            extraMass, extraAt, angle,
                                            name=name, **kw))

    # =====================================================================
    #  ZŁĄCZA
    # =====================================================================
    def fixed(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> FixedJoint:
        """SPAW - dwa ciała stają się jedną bryłą."""
        return self._register(FixedJoint(b0, b1, anchor, **kw))

    def revolute(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> RevoluteJoint:
        """ZAWIAS - wspólny punkt, obrót swobodny lub ograniczony."""
        return self._register(RevoluteJoint(b0, b1, anchor, **kw))

    def rope(self, b0: Body, b1: Body, anchor0: Vec2, anchor1: Vec2,
             **kw) -> RopeJoint:
        """LINKA (unilateral) albo PRĘT (unilateral=False)."""
        return self._register(RopeJoint(b0, b1, anchor0, anchor1, **kw))

    def spring(self, b0: Body, b1: Body, anchor0: Vec2, anchor1: Vec2,
               **kw) -> SpringJoint:
        return self._register(SpringJoint(b0, b1, anchor0, anchor1, **kw))

    def motor(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> MotorJoint:
        return self._register(MotorJoint(b0, b1, anchor, **kw))

    def prismatic(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> PrismaticJoint:
        return self._register(PrismaticJoint(b0, b1, anchor, **kw))

    # =====================================================================
    #  KONSTRUKCJE ZŁOŻONE
    # =====================================================================
    def ropeChain(self, b0: Body, anchor0: Vec2, b1: Body, anchor1: Vec2,
                  numNodes: int = 4, nodeMass: Optional[float] = None,
                  length: Optional[float] = None, compliance: float = 0.0,
                  tag: str = "", namePrefix: str = "ogniwo") -> List[PointMass]:
        """LINA Z OGNIW: b0 --o--o--o--o-- b1.

        Zamiast jednego więzu odległościowego robimy łańcuch mas punktowych,
        dzięki czemu lina naprawdę zwisa i faluje.

        TU SIĘ STROI ROZCIĄGLIWOŚĆ LINY
        -------------------------------
        Solver jest typu Gauss-Seidel: przechodzi po więzach po kolei. Przy
        skrajnym stosunku mas (ogniwo 0.001 kg trzymające 100 kg) informacja
        o sile nie zdąży przejść przez łańcuch w jednym przejściu i lina się
        "gumuje" - mimo że compliance = 0, czyli formalnie jest nierozciągliwa.

        Zmierzone (ładunek 100 kg, 5 ogniw, 40 podkroków):
            masa ogniwa 0.001 kg -> 169 % rozciągnięcia
                        0.01  kg ->  16 %
                        0.1   kg ->   1.2 %
                        0.5   kg ->   0.17 %
                        2.0   kg ->   0.04 %

        REGUŁA KCIUKA: masa ogniwa >= masa ładunku / 100.
        nodeMass = None -> masa dobierana automatycznie (ładunek / 50).
        Za małą masę podnosimy z komunikatem, żeby scena nie psuła się po cichu.

        Pozostałe pokrętła (słabsze): World numSubSteps, numIterations,
        oraz numNodes (mniej ogniw = sztywniejsza lina, ładniejszy zwis przy
        większej liczbie).
        """
        loadMass = b1.mass if b1.mass > 0.0 else b0.mass
        if nodeMass is None:
            nodeMass = max(loadMass / 50.0, 1e-3)
        minMass = loadMass / 100.0
        if loadMass > 0.0 and nodeMass < minMass:
            print(f"[builder] masa ogniwa {nodeMass:g} kg za mała wobec "
                  f"ładunku {loadMass:g} kg -> podnoszę do {minMass:g} kg")
            nodeMass = minMass

        if length is None:
            length = Vec2().subtractVectors(anchor1, anchor0).length()
        seg = length / (numNodes + 1)

        # ogniwa rozkładamy wzdłuż prostej łączącej zaczepy, żeby w chwili
        # t = 0 żaden więz nie był naruszony (inaczej scena "szarpie" na starcie)
        direction = Vec2().subtractVectors(anchor1, anchor0)
        dl = direction.length()
        direction.scale(1.0 / dl if dl > 0.0 else 0.0)

        nodes: List[PointMass] = []
        prevBody, prevPoint = b0, anchor0
        for i in range(numNodes):
            p = anchor0.clone().add(direction, seg * (i + 1))
            node = self.pointMass(f"{namePrefix}{i}", p.x, p.y, nodeMass, 0.03,
                                  color=(225, 225, 225))
            self.rope(prevBody, node, prevPoint, p, length=seg,
                      compliance=compliance, tag=tag)
            nodes.append(node)
            prevBody, prevPoint = node, p
        self.rope(prevBody, b1, prevPoint, anchor1, length=seg,
                  compliance=compliance, tag=tag)
        return nodes

    def truss(self, name: str, points: List[Vec2], thickness: float,
              density: float, closed: bool = True, **kw) -> List[Beam]:
        """KRATOWNICA: łańcuch belek spawanych w wierzchołkach.

        points = kolejne wierzchołki. closed = True domyka figurę (trójkąt,
        czworokąt). Wszystkie połączenia to spawy, więc powstaje sztywna rama.
        """
        beams: List[Beam] = []
        n = len(points)
        last = n if closed else n - 1
        for i in range(last):
            a, b = points[i], points[(i + 1) % n]
            beams.append(self.beamBetween(f"{name}{i}", a, b, thickness,
                                          density, **kw))
        for i in range(len(beams)):
            j = (i + 1) % len(beams)
            if j == 0 and not closed:
                break
            self.fixed(beams[i], beams[j], points[(i + 1) % n])
        return beams

    # =====================================================================
    def _register(self, obj):
        self.world.add(obj)
        if isinstance(obj, Body) and obj.name:
            self.named[obj.name] = obj
        return obj

    def __getitem__(self, name: str) -> Body:
        """builder["pocisk"] - dostęp do ciała po nazwie."""
        return self.named[name]
