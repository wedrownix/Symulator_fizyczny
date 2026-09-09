"""
pbd2d/renderer.py -- warstwa prezentacji.

To JEDYNY moduł pakietu, który importuje pygame. Fizyka nic o grafice nie wie,
więc zamiana biblioteki graficznej (albo dorobienie eksportu do SVG) dotyka
tylko tego pliku.

WZORZEC: DYSPOZYTOR ZE SŁOWNIKIEM
    Zamiast łańcucha if isinstance(...) / elif ... trzymamy mapę
        typ obiektu -> funkcja rysująca
    Dodanie nowego kształtu to dopisanie JEDNEGO wpisu, bez modyfikowania
    istniejącego kodu (zasada O z SOLID: otwarte na rozszerzenie, zamknięte
    na modyfikację). Wyszukiwanie idzie po MRO, więc podklasa Beam-a
    narysuje się jak Beam, dopóki nie dostanie własnego wpisu.
"""

from __future__ import annotations
from typing import Callable, Dict, Optional, Type

import pygame

from .vector2 import Vec2
from .bodies import Body, Beam, Disk, PointMass
from .joints import (Joint, RopeJoint, RevoluteJoint, FixedJoint,
                     SpringJoint, MotorJoint, PrismaticJoint)
from .world import World


class Camera:
    """Transformacja metry <-> piksele.

    simMinWidth mówi, ile metrów ma się zmieścić w oknie; originY, na jakiej
    wysokości ekranu leży y = 0 (zwykle nisko, bo scena rośnie do góry)."""

    def __init__(self, width: int, height: int, simMinWidth: float = 6.0,
                 originX: float = 0.5, originY: float = 0.88) -> None:
        self.width = width
        self.height = height
        self.scale = min(width, height) / simMinWidth
        self.originX = originX
        self.originY = originY

    def cX(self, x: float) -> int:
        return int(self.width * self.originX + x * self.scale)

    def cY(self, y: float) -> int:
        return int(self.height * self.originY - y * self.scale)

    def toScreen(self, v: Vec2):
        return (self.cX(v.x), self.cY(v.y))

    def toWorld(self, sx: float, sy: float) -> Vec2:
        return Vec2((sx - self.width * self.originX) / self.scale,
                    (self.height * self.originY - sy) / self.scale)

    def px(self, meters: float) -> int:
        return max(1, int(meters * self.scale))


class Renderer:
    """Rysuje świat. Dobór funkcji rysującej przez słownik typów."""

    def __init__(self, surface: pygame.Surface, camera: Camera,
                 background=(28, 30, 36)) -> None:
        self.surface = surface
        self.camera = camera
        self.background = background
        self.showFrames = False      # podgląd ramek zaczepienia złączy

        # --- rejestry dyspozytora ---
        self.bodyDrawers: Dict[Type, Callable] = {
            Beam: self._drawBeam,
            Disk: self._drawDisk,
            PointMass: self._drawPointMass,
        }
        self.jointDrawers: Dict[Type, Callable] = {
            RopeJoint: self._drawRope,
            SpringJoint: self._drawSpring,
            RevoluteJoint: self._drawHinge,
            MotorJoint: self._drawMotor,
            FixedJoint: self._drawWeld,
            PrismaticJoint: self._drawSlider,
        }

    # ---- dobór funkcji po typie (z uwzględnieniem dziedziczenia) --------
    def _drawerFor(self, obj, table: Dict[Type, Callable]) -> Optional[Callable]:
        for cls in type(obj).__mro__:        # najpierw dokładny typ, potem bazowe
            fn = table.get(cls)
            if fn is not None:
                return fn
        return None

    # ---- ciała ----------------------------------------------------------
    def _drawBeam(self, b: Beam) -> None:
        pts = [self.camera.toScreen(v) for v in b.corners()]
        pygame.draw.polygon(self.surface, b.color, pts)
        pygame.draw.polygon(self.surface, (35, 35, 40), pts, 3)

    def _drawDisk(self, b: Disk) -> None:
        c = self.camera.toScreen(b.pos)
        pygame.draw.circle(self.surface, b.color, c, self.camera.px(b.radius))
        pygame.draw.circle(self.surface, (35, 35, 40), c,
                           self.camera.px(b.radius), 3)
        # promień - żeby było widać obrót koła
        pygame.draw.line(self.surface, (35, 35, 40), c,
                         self.camera.toScreen(b.rimPoint()), 3)

    def _drawPointMass(self, b: PointMass) -> None:
        pygame.draw.circle(self.surface, b.color, self.camera.toScreen(b.pos),
                           max(self.camera.px(b.radius), 4))

    # ---- złącza ---------------------------------------------------------
    def _drawRope(self, j: RopeJoint) -> None:
        color = (238, 238, 238) if not j.disabled else (110, 80, 80)
        pygame.draw.line(self.surface, color,
                         self.camera.toScreen(j.globalPos0),
                         self.camera.toScreen(j.globalPos1), 3)

    def _drawSpring(self, j: SpringJoint) -> None:
        pygame.draw.line(self.surface, (150, 220, 150),
                         self.camera.toScreen(j.globalPos0),
                         self.camera.toScreen(j.globalPos1), 4)

    def _drawHinge(self, j: RevoluteJoint) -> None:
        p = self.camera.toScreen(j.globalPos0)
        pygame.draw.circle(self.surface, (255, 255, 255), p, 12)
        pygame.draw.circle(self.surface, (40, 40, 45), p, 12, 3)

    def _drawMotor(self, j: MotorJoint) -> None:
        p = self.camera.toScreen(j.globalPos0)
        pygame.draw.circle(self.surface, (120, 255, 140), p, 13)
        pygame.draw.circle(self.surface, (40, 40, 45), p, 13, 3)

    def _drawWeld(self, j: FixedJoint) -> None:
        pygame.draw.circle(self.surface, (235, 90, 90),
                           self.camera.toScreen(j.globalPos0), 10, 3)

    def _drawSlider(self, j: PrismaticJoint) -> None:
        pygame.draw.line(self.surface, (255, 170, 70),
                         self.camera.toScreen(j.globalPos0),
                         self.camera.toScreen(j.globalPos1), 5)

    # ---- ramki zaczepienia (diagnostyka) --------------------------------
    def _drawFrame(self, pos: Vec2, angle: float, color, size=0.12) -> None:
        o = self.camera.toScreen(pos)
        ax = self.camera.toScreen(pos.clone().add(Vec2(size, 0).rotate(angle)))
        ay = self.camera.toScreen(pos.clone().add(Vec2(0, size).rotate(angle)))
        pygame.draw.line(self.surface, color, o, ax, 3)
        pygame.draw.line(self.surface, (color[2], color[1], color[0]), o, ay, 3)

    # ---- całość ---------------------------------------------------------
    def draw(self, world: World, groundY: Optional[float] = None) -> None:
        self.surface.fill(self.background)

        if groundY is not None:
            y = self.camera.cY(groundY)
            pygame.draw.line(self.surface, (95, 115, 85),
                             (0, y), (self.camera.width, y), 4)

        # najpierw złącza (pod spodem), potem ciała
        for j in world.joints:
            j.updateGlobalFrames()
            if not (j.globalPos0.isFinite() and j.globalPos1.isFinite()):
                continue
            if j.disabled and not isinstance(j, RopeJoint):
                continue                    # zwolniony zawias znika z rysunku
            fn = self._drawerFor(j, self.jointDrawers)
            if fn:
                fn(j)
            if self.showFrames:
                self._drawFrame(j.globalPos0, j.globalRot0, (255, 120, 120))
                self._drawFrame(j.globalPos1, j.globalRot1, (120, 160, 255))

        for b in world.bodies:
            # bezpiecznik: ciało, które uciekło w nieskończoność, pomijamy -
            # inaczej pygame dostaje współrzędne spoza zakresu int i rysuje
            # "spłaszczone" wielokąty, co wygląda jak deformacja bryły
            if not b.isSane():
                continue
            fn = self._drawerFor(b, self.bodyDrawers)
            if fn:
                fn(b)


class Hud:
    """Prosty tekst informacyjny. Osobna klasa, żeby Renderer zajmował się
    wyłącznie sceną (S z SOLID)."""

    def __init__(self, surface: pygame.Surface, size: int = 24,
                 color=(215, 215, 225)) -> None:
        self.surface = surface
        self.font = pygame.font.SysFont("consolas", size)
        self.color = color
        self.lineHeight = int(size * 1.35)

    def draw(self, lines, x: int = 20, y: int = 18) -> None:
        for i, text in enumerate(lines):
            self.surface.blit(self.font.render(text, True, self.color),
                              (x, y + i * self.lineHeight))
