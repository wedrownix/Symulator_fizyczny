"""
pbd2d/config.py -- parametry solvera w jednym obiekcie.

DLACZEGO OSOBNY PLIK
--------------------
W poprzedniej wersji limity bezpieczeństwa (MAX_ROT_CORRECTION itd.) były
globalnymi stałymi modułu. To działało, ale łamało zasadę D z SOLID
(Dependency Inversion): klasa Body zależała od modułu, w którym akurat
mieszkała, a nie od przekazanej jej konfiguracji. Efekt praktyczny: nie dało
się mieć dwóch światów o różnych ustawieniach w jednym programie.

Teraz konfiguracja jest zwykłym obiektem, wstrzykiwanym do World, a World
rozdaje ją ciałom przy rejestracji. Dwa światy = dwie konfiguracje.
"""

from __future__ import annotations
from dataclasses import dataclass
from .vector2 import Vec2


@dataclass
class SolverConfig:
    """Parametry kroku symulacji i bezpieczniki numeryczne."""

    # ---- krok czasowy ---------------------------------------------------
    dt: float = 1.0 / 60.0
    numSubSteps: int = 40
    """POKRĘTŁO nr 2 sztywności więzów.
    Podkroki to n MAŁYCH pełnych kroków (integracja + więzy + prędkości),
    a nie n iteracji solvera w jednym dużym kroku. Błąd więzów maleje mniej
    więcej jak 1/n^2, koszt rośnie liniowo. Pierwsza rzecz do podkręcenia,
    gdy linki się rozciągają."""

    numIterations: int = 1
    """POKRĘTŁO nr 3: dodatkowe przejścia po więzach WEWNĄTRZ podkroku.
    Przy tym samym koszcie działa słabiej niż podkroki, ale bywa przydatne,
    gdy dt jest już bardzo małe."""

    # ---- bezpieczniki numeryczne ---------------------------------------
    # Nie są fizyką - są zabezpieczeniem przed lawiną przy patologicznych
    # danych (ogromne naruszenie więzu, absurdalny stosunek mas).
    # W poprawnie zestrojonej scenie nigdy się nie aktywują.
    maxRotCorrection: float = 0.5
    """[rad] Maksymalny obrót z JEDNEJ korekty. Korekta przyłożona daleko
    od środka masy daje przyrost kąta invI*(r x p); przy dużym p to mogą być
    radiany w jednym podkroku, co łamie założenie o małych kątach, na którym
    stoi linearyzacja - i układ zaczyna sam sobie dodawać energii."""

    maxSpeed: float = 100.0        # [m/s]
    maxOmega: float = 50.0         # [rad/s]
    maxCoord: float = 1.0e4
    """[m] Dalej uznajemy ciało za 'uciekłe' i pomijamy je w rysowaniu -
    inaczej pygame dostaje współrzędne spoza zakresu int i rysuje
    'spłaszczone' wielokąty, co wygląda jak deformacja bryły sztywnej."""


@dataclass
class WorldConfig:
    """Konfiguracja świata: konfiguracja solvera + otoczenie."""

    gravity: Vec2 = None
    solver: SolverConfig = None
    groundY: float = None
    """None = brak podłoża. Liczba = poziom gruntu; masy punktowe nie mogą
    zejść poniżej (patrz World._solveGround)."""
    groundRestitution: float = 0.0

    def __post_init__(self) -> None:
        # dataclass nie pozwala na mutowalne wartości domyślne, stąd None
        if self.gravity is None:
            self.gravity = Vec2(0.0, -9.81)
        if self.solver is None:
            self.solver = SolverConfig()
