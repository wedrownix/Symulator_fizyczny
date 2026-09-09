"""
pbd2d/vector2.py -- algebra wektorowa 2D.

Warstwa najniższa: nie zależy od niczego w projekcie i nic o fizyce nie wie.
Można ją testować i używać osobno.

KONWENCJA (ważna, obowiązuje w całym pakiecie):
    metody MUTUJĄCE zwracają self          -> płynne API, zero alokacji
    metody z przyrostkiem -ed zwracają kopię
        v.rotate(a)   zmienia v
        v.rotated(a)  zwraca nowy wektor, v bez zmian
Zero alokacji ma znaczenie praktyczne: solver wykonuje setki tysięcy operacji
wektorowych na sekundę, więc tworzenie nowych obiektów zabijałoby wydajność.
"""

from __future__ import annotations
import math


class Vec2:
    """Wektor 2D."""

    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    # ---- kopiowanie -----------------------------------------------------
    def clone(self) -> "Vec2":
        return Vec2(self.x, self.y)

    def set(self, v: "Vec2") -> "Vec2":
        self.x, self.y = v.x, v.y
        return self

    # ---- działania mutujące ---------------------------------------------
    def add(self, v: "Vec2", s: float = 1.0) -> "Vec2":
        """self += v * s   (odpowiednik addScaledVector z three.js)"""
        self.x += v.x * s
        self.y += v.y * s
        return self

    def subtract(self, v: "Vec2", s: float = 1.0) -> "Vec2":
        self.x -= v.x * s
        self.y -= v.y * s
        return self

    def addVectors(self, a: "Vec2", b: "Vec2") -> "Vec2":
        self.x, self.y = a.x + b.x, a.y + b.y
        return self

    def subtractVectors(self, a: "Vec2", b: "Vec2") -> "Vec2":
        self.x, self.y = a.x - b.x, a.y - b.y
        return self

    def scale(self, s: float) -> "Vec2":
        self.x *= s
        self.y *= s
        return self

    def normalize(self) -> "Vec2":
        d = self.length()
        if d > 0.0:
            self.x /= d
            self.y /= d
        return self

    def rotate(self, angle: float) -> "Vec2":
        """Obrót o kąt [rad]. W 3D robił to applyQuaternion(rot);
        obrót o -angle zastępuje applyQuaternion(invRot), więc w 2D
        nie trzeba w ogóle trzymać odwrotnej orientacji."""
        c, s = math.cos(angle), math.sin(angle)
        self.x, self.y = c * self.x - s * self.y, s * self.x + c * self.y
        return self

    # ---- wersje niemutujące ---------------------------------------------
    def rotated(self, angle: float) -> "Vec2":
        return self.clone().rotate(angle)

    def normalized(self) -> "Vec2":
        return self.clone().normalize()

    # ---- miary ----------------------------------------------------------
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def lengthSq(self) -> float:
        return self.x * self.x + self.y * self.y

    def dot(self, v: "Vec2") -> float:
        return self.x * v.x + self.y * v.y

    def cross(self, v: "Vec2") -> float:
        """W 3D iloczyn wektorowy daje wektor; w 2D oba wektory leżą
        w płaszczyźnie XY, więc wynik ma tylko składową z - jest LICZBĄ.
        To uproszczenie usuwa z kodu połowę algebry wersji 3D."""
        return self.x * v.y - self.y * v.x

    def perp(self) -> "Vec2":
        """Wektor prostopadły (-y, x), czyli obrót o +90 stopni."""
        return Vec2(-self.y, self.x)

    def isFinite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)

    def __repr__(self) -> str:
        return f"Vec2({self.x:.4f}, {self.y:.4f})"


def normalizeAngle(a: float) -> float:
    """Kąt do przedziału (-pi, pi].

    Konieczne, bo kąt ciała rośnie bez ograniczeń (koło po 10 obrotach ma
    rot = 62.8). Bez normalizacji różnica kątów wyszłaby np. 6.2 zamiast
    -0.08 i spaw szarpnąłby ciałem o pełny obrót."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)
