"""
pbd2d/world.py -- World: SOLVER i nic więcej.

ROZDZIELENIE ODPOWIEDZIALNOŚCI (zasada S z SOLID)
    Wcześniej World robił dwie rzeczy naraz: liczył fizykę i udostępniał
    wygodne metody do budowania scen (addBeam, connectRope...). To dwa różne
    powody do zmiany tej samej klasy.

    Teraz:
        World         -- trzyma listy ciał i złączy, wykonuje krok czasowy,
                         zwalnia więzy. Zmienia się, gdy zmienia się ALGORYTM.
        SceneBuilder  -- fabryka: tworzy ciała i złącza, nazywa je, pilnuje
                         poprawności parametrów. Zmienia się, gdy zmienia się
                         WYGODA BUDOWANIA (builder.py).

    World nie wie o istnieniu SceneBuilder-a. Zależność idzie w jedną stronę,
    więc solver da się użyć bez buildera (np. w testach jednostkowych).
"""

from __future__ import annotations
from typing import Callable, Dict, Iterator, List, Optional

from .vector2 import Vec2
from .config import WorldConfig, SolverConfig
from .bodies import Body, PointMass
from .joints import Joint


class World:
    """Świat symulacji: zbiór ciał + zbiór więzów + pętla czasowa.

    PĘTLA (slajdy "XPBD Algorithm for Rigid Bodies" + "Velocity Step"):

        for n sub-steps:
            for all bodies:  integrate v, x, omega, q
            for iterations:
                for all joints:  solve()
            for all bodies:  update v, omega
            for all joints:  solveVelocity()   (tłumienie, napędy)
    """

    def __init__(self, config: Optional[WorldConfig] = None) -> None:
        self.config = config or WorldConfig()
        self.bodies: List[Body] = []
        self.joints: List[Joint] = []
        self.time = 0.0                      # czas symulacji [s]

        # obserwatorzy kroku: funkcje wołane po każdej klatce.
        # Tym mechanizmem podpina się Analyzer, nie ruszając solvera.
        self._observers: List[Callable[["World"], None]] = []

    # ---- konfiguracja jako właściwości (wygoda) -------------------------
    @property
    def solver(self) -> SolverConfig:
        return self.config.solver

    @property
    def gravity(self) -> Vec2:
        return self.config.gravity

    @property
    def dt(self) -> float:
        return self.config.solver.dt

    # ---- rejestracja ----------------------------------------------------
    def add(self, obj):
        """Dyspozytor: kieruje obiekt do właściwej kolekcji.

        Przy okazji wstrzykuje ciału konfigurację solvera - dzięki temu ciało
        nie sięga po globalne stałe, tylko dostaje je od świata, do którego
        należy (zasada D z SOLID)."""
        if isinstance(obj, Joint):
            self.joints.append(obj)
        elif isinstance(obj, Body):
            obj.config = self.config.solver
            self.bodies.append(obj)
        else:
            raise TypeError(f"Nieobsługiwany obiekt: {type(obj)}")
        return obj

    def remove(self, obj) -> None:
        if obj in self.joints:
            self.joints.remove(obj)
        elif obj in self.bodies:
            self.bodies.remove(obj)

    def clear(self) -> None:
        self.bodies.clear()
        self.joints.clear()
        self.time = 0.0

    def __iter__(self) -> Iterator:
        """Świat jest iterowalny po wszystkich obiektach (wzorzec Iterator).
        Przydaje się przy zapisie sceny i przy diagnostyce."""
        yield from self.bodies
        yield from self.joints

    # ---- zwalnianie więzów ---------------------------------------------
    def release(self, tag: str) -> int:
        """Zwalnia (wyłącza) wszystkie więzy o podanej etykiecie.

        Tak realizuje się "przecięcie liny" w trakcie symulacji: nie usuwamy
        obiektu, tylko ustawiamy disabled = True. Obiekt zostaje w historii,
        więc Analyzer nadal wie, co i kiedy zostało zwolnione, a rysowanie
        może to pokazać innym kolorem.

        Zwraca liczbę zwolnionych więzów (0 = nie było takiej etykiety)."""
        n = 0
        for j in self.joints:
            if j.tag == tag and not j.disabled:
                j.disabled = True
                n += 1
        return n

    def restore(self, tag: str) -> int:
        """Odwrotność release - przydatne przy testach 'co gdyby'."""
        n = 0
        for j in self.joints:
            if j.tag == tag and j.disabled:
                j.disabled = False
                n += 1
        return n

    def tags(self) -> Dict[str, int]:
        """Wszystkie etykiety więzów wraz z liczbą aktywnych - do podglądu
        w interfejsie ("co jeszcze mogę zwolnić")."""
        out: Dict[str, int] = {}
        for j in self.joints:
            if j.tag:
                out[j.tag] = out.get(j.tag, 0) + (0 if j.disabled else 1)
        return out

    def find(self, name: str) -> Optional[Body]:
        for b in self.bodies:
            if b.name == name:
                return b
        return None

    # ---- obserwatorzy ---------------------------------------------------
    def addObserver(self, fn: Callable[["World"], None]) -> None:
        """Rejestruje funkcję wołaną po każdym pełnym kroku (wzorzec
        Obserwator). Tak podpina się Analyzer - solver o nim nie wie."""
        self._observers.append(fn)

    # ---- podłoże --------------------------------------------------------
    def _solveGround(self) -> None:
        """Prosta reakcja gruntu dla mas punktowych.

        WAŻNE: robione PO updateVelocities, a nie razem z więzami. Gdyby
        wepchnąć ciało z powrotem PRZED odtworzeniem prędkości, to korekta
        1 cm w podkroku 1/2400 s dałaby prędkość 24 m/s wziętą znikąd."""
        cfg = self.config
        if cfg.groundY is None:
            return
        for b in self.bodies:
            if b.isStatic or not isinstance(b, PointMass):
                continue
            minY = cfg.groundY + b.radius
            if b.pos.y < minY:
                b.pos.y = minY
                b.prevPos.y = minY
                if b.vel.y < 0.0:
                    b.vel.y = -b.vel.y * cfg.groundRestitution

    # ---- krok symulacji -------------------------------------------------
    def simulate(self) -> None:
        s = self.solver
        sdt = s.dt / s.numSubSteps
        for _ in range(s.numSubSteps):
            for b in self.bodies:
                b.integrate(sdt, self.gravity)
            for _ in range(s.numIterations):
                for j in self.joints:
                    j.solve()
            for b in self.bodies:
                b.updateVelocities()
            self._solveGround()
            for j in self.joints:
                if not j.disabled:
                    j.solveVelocity(sdt)
        self.time += s.dt

        for observe in self._observers:
            observe(self)

    # ---- energie (dla Analyzera i diagnostyki) --------------------------
    def kineticEnergy(self) -> float:
        return sum(b.kineticEnergy() for b in self.bodies)

    def potentialEnergy(self, refY: float = 0.0) -> float:
        g = -self.gravity.y
        return sum(b.potentialEnergy(g, refY) for b in self.bodies)

    def mechanicalEnergy(self, refY: float = 0.0) -> float:
        """Energia całkowita układu. W idealnym świecie stała - jej dryf jest
        najlepszą miarą jakości symulacji (za mało podkroków -> dryf rośnie)."""
        return self.kineticEnergy() + self.potentialEnergy(refY)
