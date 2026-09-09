"""
main.py -- program główny: pętla pygame, sterowanie, podpięcie Analyzera.

Ten plik NIE zawiera fizyki ani definicji scen. Jego rola to spiąć warstwy:
    scena (scenes/*)  ->  World (solver)  ->  Renderer (obraz)
                                          ->  Analyzer (liczby)

STEROWANIE
    SPACJA   zwolnij procę (pocisk odlatuje)   = world.release("proca")
    C        zwolnij przeciwwagę
    1 / 2    wybór sceny: trebusz / maszyny
    A        automatyczne zwolnienie ON/OFF (przy zadanym kącie ramienia)
    R        restart sceny
    P        pauza
    F        podgląd ramek zaczepienia złączy
    S        zapis danych: analiza.csv + analiza.png + podsumowanie w konsoli
    ESC      wyjście
"""

from __future__ import annotations
import math
import sys

import pygame

from pbd2d import Vec2, World, WorldConfig, SolverConfig, Analyzer
from pbd2d.renderer import Camera, Renderer, Hud
from scenes import trebuchet, machines

# --- rozmiar okna: 3200x2000 pod duży monitor; zmniejsz, jeśli trzeba -------
SCREEN_W, SCREEN_H = 3200, 2000

pygame.init()
win = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Symulator brył sztywnych 2D - XPBD")
clock = pygame.time.Clock()


# =============================================================================
#  APLIKACJA
# =============================================================================

class App:
    """Spina warstwy i obsługuje wejście. Cała zmienność interfejsu siedzi
    tutaj, więc silnik pozostaje niezależny od pygame."""

    def __init__(self) -> None:
        # konfiguracja solvera: to są pokrętła sztywności więzów
        self.config = WorldConfig(
            gravity=Vec2(0.0, -9.81),
            solver=SolverConfig(dt=1.0 / 60.0,
                                numSubSteps=40,     # POKRĘTŁO nr 2
                                numIterations=1),   # POKRĘTŁO nr 3
            groundY=0.0,
            groundRestitution=0.0,
        )
        self.world = World(self.config)
        self.camera = Camera(SCREEN_W, SCREEN_H, simMinWidth=7.0,
                             originX=0.35, originY=0.88)
        self.renderer = Renderer(win, self.camera)
        self.hud = Hud(win, size=26)

        self.sceneName = "trebusz"
        self.paused = False
        self.autoRelease = True
        self.analyzer: Analyzer = None
        self.builder = None
        self.setupScene("trebusz")

    # ---- scena ----------------------------------------------------------
    def setupScene(self, name: str) -> None:
        self.sceneName = name
        self.world.clear()
        self.world._observers.clear()        # nowa scena = nowy analizator

        if name == "trebusz":
            self.params = trebuchet.TrebuchetParams()
            self.builder = trebuchet.build(self.world, self.params)
            tracked = self.builder["pocisk"]
            arm = self.builder["ramie"]
        else:
            self.builder = machines.build(self.world)
            tracked = self.builder["kulka"]
            arm = self.builder["dzwignia"]

        # Analyzer podpina się jako OBSERWATOR - solver nic o nim nie wie
        self.analyzer = Analyzer(self.world, tracked, arm, refY=0.0)
        self.world.addObserver(self.analyzer)

    # ---- spust ----------------------------------------------------------
    def release(self, tag: str) -> None:
        """Zwolnienie więzów o danej etykiecie + zapis zdarzenia w analizie."""
        n = self.world.release(tag)
        if n:
            ev = self.analyzer.mark(f"zwolnienie: {tag}")
            print(f"[{self.world.time:6.2f} s] zwolniono {n} więzów '{tag}'"
                  f"  v = {ev.speed:.2f} m/s   Ek = {ev.ek:.1f} J")

    def autoReleaseCheck(self) -> None:
        """Automatyczny spust przy zadanym kącie ramienia - tak działa
        prawdziwy trebusz (hak zsuwa się z bolca w ustalonym położeniu)."""
        if self.sceneName != "trebusz" or not self.autoRelease:
            return
        if self.analyzer.launch is not None:
            return
        if self.builder["ramie"].rot < self.params.releaseAngle:
            self.release("proca")

    # ---- zapis wyników --------------------------------------------------
    def saveResults(self) -> None:
        csvPath = self.analyzer.saveCsv(f"analiza_{self.sceneName}.csv")
        pngPath = self.analyzer.savePlot(f"analiza_{self.sceneName}.png")
        print(self.analyzer.summary())
        print(f"dane  -> {csvPath}")
        if pngPath:
            print(f"wykres -> {pngPath}")

    # ---- wejście --------------------------------------------------------
    def handleKey(self, key: int) -> bool:
        if key == pygame.K_ESCAPE:
            return False
        elif key == pygame.K_SPACE:
            self.release("proca" if self.sceneName == "trebusz" else "lina")
        elif key == pygame.K_c:
            self.release("przeciwwaga")
        elif key == pygame.K_1:
            self.setupScene("trebusz")
        elif key == pygame.K_2:
            self.setupScene("maszyny")
        elif key == pygame.K_a:
            self.autoRelease = not self.autoRelease
        elif key == pygame.K_r:
            self.setupScene(self.sceneName)
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_f:
            self.renderer.showFrames = not self.renderer.showFrames
        elif key == pygame.K_s:
            self.saveResults()
        return True

    # ---- HUD ------------------------------------------------------------
    def hudLines(self):
        a = self.analyzer
        s = a.samples[-1] if a.samples else None
        tags = ", ".join(f"{k}({v})" for k, v in self.world.tags().items())
        lines = [
            f"scena: {self.sceneName}    t = {self.world.time:5.2f} s"
            f"    {'PAUZA' if self.paused else ''}",
            f"śledzone ciało: {a.body.name}  v = {s.speed:6.2f} m/s"
            f"   Ek = {s.ekBody:8.2f} J" if s else "",
            f"energia zgromadzona: {a.storedEnergy:8.1f} J"
            f"    Ek układu: {s.ekTotal:8.1f} J"
            f"    E całkowita: {s.eTotal:8.1f} J" if s else "",
            f"aktywne więzy do zwolnienia: {tags}",
        ]
        ev = a.launch
        if ev:
            lines.append(
                f"ZWOLNIONO w t={ev.t:.2f}s:  v0 = {ev.speed:.2f} m/s"
                f"   Ek0 = {ev.ek:.1f} J   sprawność = {a.efficiency():.1f} %"
                f"   zasięg = {a.ballisticRange():.1f} m")
        lines.append("SPACJA zwolnij | C przeciwwaga | 1/2 scena | A auto | "
                     "R restart | P pauza | F ramki | S zapis")
        return [l for l in lines if l]

    # ---- pętla ----------------------------------------------------------
    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self.handleKey(event.key)

            if not self.paused:
                self.world.simulate()      # tu Analyzer dostaje próbkę
                self.autoReleaseCheck()

            self.renderer.draw(self.world, groundY=self.config.groundY)
            self.hud.draw(self.hudLines())
            pygame.display.update()
            clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    App().run()
