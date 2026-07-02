"""
Collisions.py
--------------
Symulacja 2D sprezystych kolizji kul (Ten Minute Physics, odcinek 03 - Billiard,
Matthias Muller) - wersja przebudowana pod katem dobrych praktyk OOP.

Wzorce projektowe i zasady zastosowane w tym pliku
----------------------------------------------------
- SRP  (Single Responsibility) -> kazda klasa ma jeden powod do zmiany:
      Vector2            - matematyka wektorowa
      Ball               - stan i ruch pojedynczego ciala
      BallFactory        - tworzenie obiektow Ball
      CollisionResolver  - wykrywanie i rozwiazywanie kolizji
      PhysicsScene       - stan swiata fizycznego
      Renderer           - rysowanie
      EventDispatcher    - routing zdarzen Pygame
      Simulation         - orkiestracja petli gry
- OCP  (Open/Closed)  -> SimulatedBody to punkt rozszerzenia: kolejne typy cial
      (przeszkody, flippery, klocki trebusza w nastepnych etapach projektu)
      dochodza przez dziedziczenie, bez modyfikacji PhysicsScene ani Renderer.
- DIP  (Dependency Inversion) -> CollisionResolver nie odwoluje sie do zadnej
      zmiennej globalnej, tylko dostaje wszystko czego potrzebuje (world_size,
      restitution) przez konstruktor - mozna go przetestowac w izolacji.
- Fluent Interface -> Vector2 (metody modyfikujace zwracaja self, mozna je
      laczyc w lancuch, np. Vector2().subtract_vectors(a, b).scale(0.5)).
- Singleton        -> PhysicsScene (jeden, wspolny stan swiata fizycznego).
- Fabryka (Factory)-> BallFactory centralizuje logike tworzenia losowych kul.
- Iterator         -> PhysicsScene.__iter__ pozwala pisac "for ball in scene".
- Dyspozytor (Dispatch) -> EventDispatcher mapuje zdarzenia Pygame na handlery
      zamiast rozrastajacego sie if/elif w petli glownej.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import Callable, Dict, Iterator, List

import pygame

pygame.init()

# ---------------------------------------------------------------------------
# Konfiguracja okna i skali swiata (metry <-> piksele)
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
SIM_MIN_WIDTH = 20  # najkrotszy bok okna odpowiada tylu metrom swiata fizycznego
CSCALE = min(SCREEN_WIDTH, SCREEN_HEIGHT) / SIM_MIN_WIDTH
SIM_WIDTH = SCREEN_WIDTH / CSCALE
SIM_HEIGHT = SCREEN_HEIGHT / CSCALE


# ---------------------------------------------------------------------------
# Matematyka wektorowa
# ---------------------------------------------------------------------------
class Vector2:
    """Wektor 2D. Metody modyfikujace stan zwracaja self (Fluent Interface)."""

    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    def clone(self) -> Vector2:
        return Vector2(self.x, self.y)

    def set(self, other: Vector2) -> Vector2:
        self.x, self.y = other.x, other.y
        return self

    def add(self, other: Vector2, scale: float = 1.0) -> Vector2:
        self.x += other.x * scale
        self.y += other.y * scale
        return self

    def add_vectors(self, a: Vector2, b: Vector2) -> Vector2:
        self.x = a.x + b.x
        self.y = a.y + b.y
        return self

    def subtract(self, other: Vector2, scale: float = 1.0) -> Vector2:
        self.x -= other.x * scale
        self.y -= other.y * scale
        return self

    def subtract_vectors(self, a: Vector2, b: Vector2) -> Vector2:
        self.x = a.x - b.x
        self.y = a.y - b.y
        return self

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def scale(self, s: float) -> Vector2:
        self.x *= s
        self.y *= s
        return self

    def dot(self, other: Vector2) -> float:
        return self.x * other.x + self.y * other.y

    def __repr__(self) -> str:
        return f"Vector2({self.x:.3f}, {self.y:.3f})"


# ---------------------------------------------------------------------------
# Ciala symulacji
# ---------------------------------------------------------------------------
class SimulatedBody(ABC):
    """Wspolny interfejs dla wszystkich obiektow sceny symulacji.

    Punkt rozszerzenia pod zasade OCP: kolejne etapy projektu (przeszkody,
    flippery, klocki trebusza) doloza kolejne podklasy bez koniecznosci
    zmieniania PhysicsScene ani Renderer."""

    @abstractmethod
    def simulate(self, gravity: Vector2, dt: float) -> None:
        ...


class Ball(SimulatedBody):
    """Pojedyncza kula - promien, masa, pozycja i predkosc."""

    __slots__ = ("radius", "mass", "pos", "vel")

    def __init__(self, radius: float, mass: float, pos: Vector2, vel: Vector2) -> None:
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.vel = vel.clone()

    def simulate(self, gravity: Vector2, dt: float) -> None:
        """Calkowanie Eulera pierwszego rzedu: v += g*dt, x += v*dt."""
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)

    def __repr__(self) -> str:
        return f"Ball(r={self.radius:.2f}, pos={self.pos}, vel={self.vel})"


class BallFactory:
    """Fabryka kul: centralizuje logike tworzenia losowych obiektow Ball,
    zamiast rozrzucac ja w kodzie konfiguracji sceny."""

    @staticmethod
    def create_random(
        world_size: Vector2,
        min_radius: float = 0.5,
        max_radius: float = 1.0,
        min_speed: float = -1.0,
        max_speed: float = 3.0,
    ) -> Ball:
        radius = min_radius + random.random() * (max_radius - min_radius)
        mass = math.pi * radius * radius

        pos = Vector2(
            random.random() * world_size.x,
            random.random() * world_size.y,
        )

        speed_range = max_speed - min_speed
        vel = Vector2(
            min_speed + random.random() * speed_range,
            min_speed + random.random() * speed_range,
        )

        return Ball(radius, mass, pos, vel)


# ---------------------------------------------------------------------------
# Kolizje
# ---------------------------------------------------------------------------
class CollisionResolver:
    """Wykrywanie i rozwiazywanie kolizji. Nie odwoluje sie do zadnego stanu
    globalnego - wszystko, czego potrzebuje, dostaje w konstruktorze (DIP),
    dzieki czemu mozna go przetestowac w izolacji od reszty programu."""

    def __init__(self, world_size: Vector2, restitution: float) -> None:
        self.world_size = world_size
        self.restitution = restitution

    def resolve_ball_ball(self, b1: Ball, b2: Ball) -> None:
        normal = Vector2().subtract_vectors(b2.pos, b1.pos)
        distance = normal.length()

        if distance == 0.0 or distance > b1.radius + b2.radius:
            return

        normal.scale(1.0 / distance)

        # Korekta nakladajacych sie pozycji (positional correction)
        overlap = (b1.radius + b2.radius - distance) / 2.0
        b1.pos.add(normal, -overlap)
        b2.pos.add(normal, overlap)

        v1 = b1.vel.dot(normal)
        v2 = b2.vel.dot(normal)
        m1, m2 = b1.mass, b2.mass
        r = self.restitution

        new_v1 = (m1 * v1 + m2 * v2 - m2 * (v1 - v2) * r) / (m1 + m2)
        new_v2 = (m1 * v1 + m2 * v2 - m1 * (v2 - v1) * r) / (m1 + m2)

        b1.vel.add(normal, new_v1 - v1)
        b2.vel.add(normal, new_v2 - v2)

    def resolve_ball_wall(self, ball: Ball) -> None:
        w = self.world_size

        if ball.pos.x < ball.radius:
            ball.pos.x = ball.radius
            ball.vel.x *= -1
        elif ball.pos.x > w.x - ball.radius:
            ball.pos.x = w.x - ball.radius
            ball.vel.x *= -1

        if ball.pos.y < ball.radius:
            ball.pos.y = ball.radius
            ball.vel.y *= -1
        elif ball.pos.y > w.y - ball.radius:
            ball.pos.y = w.y - ball.radius
            ball.vel.y *= -1


# ---------------------------------------------------------------------------
# Swiat fizyczny
# ---------------------------------------------------------------------------
class PhysicsScene:
    """Stan swiata fizycznego. Singleton - w calym programie istnieje
    dokladnie jedna scena; kolejne wywolania PhysicsScene() zwracaja te sama
    instancje.

    Uwaga (do dyskusji): Singleton bywa krytykowany, bo utrudnia testowanie
    (globalny stan dzielony miedzy testami) i uniemozliwia posiadanie np.
    dwoch niezaleznych symulacji naraz. Tu jest uzasadniony charakterem
    programu (jedno okno = jeden swiat), ale w wiekszym projekcie (np. wiele
    scen/poziomow trebusza) lepszym rozwiazaniem bylby wstrzykiwany (dependency
    injection) obiekt sceny zamiast globalnego Singletona."""

    _instance: PhysicsScene | None = None

    def __new__(cls) -> PhysicsScene:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.gravity = Vector2(0, -10)
        self.dt = 1.0 / 60.0
        self.world_size = Vector2(SIM_WIDTH, SIM_HEIGHT)
        self.restitution = 0.9
        self.balls: List[Ball] = []
        self.collision_resolver = CollisionResolver(self.world_size, self.restitution)

    def populate_randomly(self, num_balls: int = 20) -> None:
        self.balls = [BallFactory.create_random(self.world_size) for _ in range(num_balls)]

    def step(self) -> None:
        """Jeden krok symulacji: ruch wszystkich cial + rozwiazanie kolizji."""
        for i, ball in enumerate(self.balls):
            ball.simulate(self.gravity, self.dt)

            for other in self.balls[i + 1:]:
                self.collision_resolver.resolve_ball_ball(ball, other)

            self.collision_resolver.resolve_ball_wall(ball)

    def __iter__(self) -> Iterator[Ball]:
        return iter(self.balls)

    def __len__(self) -> int:
        return len(self.balls)


# ---------------------------------------------------------------------------
# Rysowanie
# ---------------------------------------------------------------------------
class Renderer:
    """Odpowiada wylacznie za rysowanie stanu swiata na ekranie (SRP) -
    nie zna regul fizyki ani obslugi wejscia."""

    def __init__(self, win: "pygame.Surface", scale: float, screen_height: int) -> None:
        self.win = win
        self.scale = scale
        self.screen_height = screen_height

    def to_screen_x(self, x: float) -> float:
        return x * self.scale

    def to_screen_y(self, y: float) -> float:
        return self.screen_height - y * self.scale

    def draw(self, scene: PhysicsScene) -> None:
        self.win.fill((30, 30, 30))
        for ball in scene:
            pygame.draw.circle(
                self.win,
                (255, 0, 0),
                (self.to_screen_x(ball.pos.x), self.to_screen_y(ball.pos.y)),
                int(ball.radius * self.scale),
            )
        pygame.display.flip()


# ---------------------------------------------------------------------------
# Wejscie / zdarzenia
# ---------------------------------------------------------------------------
class EventDispatcher:
    """Mapuje typy zdarzen Pygame na funkcje obslugi (wzorzec Dyspozytor).
    Obecnie obslugiwany jest tylko QUIT, ale dodanie np. reakcji na klik
    myszy sprowadza sie do jednej linijki register() i osobnej metody
    handlera - bez rozrastajacego sie if/elif w petli glownej."""

    def __init__(self) -> None:
        self._handlers: Dict[int, Callable[["pygame.event.Event"], None]] = {}

    def register(self, event_type: int, handler: Callable[["pygame.event.Event"], None]) -> None:
        self._handlers[event_type] = handler

    def dispatch(self, event: "pygame.event.Event") -> None:
        handler = self._handlers.get(event.type)
        if handler is not None:
            handler(event)


# --------------------------------------------------------------------------
# Orkiestracja
# --------------------------------------------------------------------------
class Simulation:
    """Spina scene / renderer / dispatcher i zawiera petle glowna.

    Tworzenie okna Pygame zostalo przeniesione tutaj (z poziomu modulu) -
    dzieki temu plik mozna bezpiecznie zaimportowac (np. w testach jednostkowych
    klas Vector2/Ball/CollisionResolver) bez efektu ubocznego w postaci
    otwierania okna."""

    def __init__(self, num_balls: int = 20) -> None:
        self.win = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Nauka_Symulatora")
        self.clock = pygame.time.Clock()

        self.scene = PhysicsScene()
        self.scene.populate_randomly(num_balls)

        self.renderer = Renderer(self.win, CSCALE, SCREEN_HEIGHT)

        self.dispatcher = EventDispatcher()
        self.dispatcher.register(pygame.QUIT, self._on_quit)

        self.running = False

    def _on_quit(self, event: "pygame.event.Event") -> None:
        self.running = False

    def handle_events(self) -> None:
        for event in pygame.event.get():
            self.dispatcher.dispatch(event)

    def run(self) -> None:
        self.running = True
        while self.running:
            self.handle_events()
            self.scene.step()
            self.renderer.draw(self.scene)
            self.clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    Simulation().run()