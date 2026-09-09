"""
pbd2d/analyzer.py -- Analyzer: pomiar i analiza ruchu.

PO CO
    Symulacja ma nie tylko ładnie wyglądać, ale dawać LICZBY: energię
    kinetyczną pocisku w funkcji kąta ramienia, prędkość w chwili zwolnienia,
    bilans energii układu, zasięg. Analyzer zbiera te dane w trakcie
    symulacji i potrafi je zapisać do CSV albo narysować wykres.

WZORZEC: OBSERWATOR
    Analyzer NIE jest częścią solvera. Rejestruje się jako obserwator:

        world.addObserver(analyzer)

    i World po każdym kroku woła go jak zwykłą funkcję (klasa ma __call__).
    Solver nic o Analyzerze nie wie, więc można go dodać, usunąć albo mieć
    kilku naraz (np. osobny dla pocisku i osobny dla przeciwwagi), nie
    dotykając ani jednej linijki fizyki.

BILANS ENERGII - jak to czytać
    E_mech = Ek + Ep, gdzie Ep = m g (y - refY).
    Na starcie układ stoi, więc E_mech = Ep i to jest "energia zgromadzona"
    (u trebusza: podniesiona przeciwwaga). W trakcie strzału ta energia
    rozdziela się między pocisk, ramię i przeciwwagę. Sprawność maszyny to
    stosunek energii pocisku w chwili zwolnienia do energii zgromadzonej.

    Dryf E_mech w czasie jest najlepszą miarą jakości symulacji: rośnie
    -> solver dodaje energię (za mało podkroków), maleje -> tłumienie.
"""

from __future__ import annotations
import csv
import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

from .vector2 import Vec2
from .bodies import Body
from .world import World


@dataclass
class Sample:
    """Jedna próbka pomiarowa - stan układu w jednej klatce."""
    t: float = 0.0                 # czas [s]
    x: float = 0.0                 # położenie śledzonego ciała [m]
    y: float = 0.0
    vx: float = 0.0                # prędkość [m/s]
    vy: float = 0.0
    speed: float = 0.0             # |v| [m/s]
    angleDeg: float = 0.0          # kierunek prędkości [stopnie]
    ekBody: float = 0.0            # energia kinetyczna śledzonego ciała [J]
    epBody: float = 0.0            # jego energia potencjalna [J]
    armAngle: float = 0.0          # kąt ramienia odniesienia [rad]
    armOmega: float = 0.0          # prędkość kątowa ramienia [rad/s]
    ekTotal: float = 0.0           # energia kinetyczna całego układu [J]
    epTotal: float = 0.0           # energia potencjalna całego układu [J]
    eTotal: float = 0.0            # energia mechaniczna całego układu [J]
    released: bool = False         # czy śledzone ciało jest już zwolnione


@dataclass
class Event:
    """Zdarzenie zaznaczone w historii (np. zwolnienie liny)."""
    t: float
    label: str
    speed: float = 0.0
    ek: float = 0.0
    armAngle: float = 0.0


class Analyzer:
    """Rejestruje ruch wybranego ciała i energie całego układu.

    Parametry:
        world     świat do obserwowania
        body      ciało śledzone szczegółowo (np. pocisk)
        arm       ciało odniesienia dla kąta (np. ramię trebusza); opcjonalne
        refY      poziom odniesienia dla energii potencjalnej [m]
        every     co która klatka ma być zapisana (1 = każda)
    """

    def __init__(self, world: World, body: Body, arm: Optional[Body] = None,
                 refY: float = 0.0, every: int = 1) -> None:
        self.world = world
        self.body = body
        self.arm = arm
        self.refY = refY
        self.every = max(1, every)

        self.samples: List[Sample] = []
        self.events: List[Event] = []
        self.released = False
        self._frame = 0

        self._initial: Optional[Sample] = None
        self.sample()                 # próbka startowa = stan zgromadzony

    # ---- interfejs obserwatora -----------------------------------------
    def __call__(self, world: World) -> None:
        """World woła to po każdym kroku (dzięki __call__ obiekt zachowuje
        się jak funkcja, więc addObserver nie potrzebuje żadnego interfejsu)."""
        self._frame += 1
        if self._frame % self.every == 0:
            self.sample()

    # ---- zbieranie danych ----------------------------------------------
    def sample(self) -> Sample:
        w, b = self.world, self.body
        g = -w.gravity.y
        s = Sample(
            t=w.time,
            x=b.pos.x, y=b.pos.y,
            vx=b.vel.x, vy=b.vel.y,
            speed=b.vel.length(),
            angleDeg=math.degrees(math.atan2(b.vel.y, b.vel.x)),
            ekBody=b.kineticEnergy(),
            epBody=b.potentialEnergy(g, self.refY),
            armAngle=self.arm.rot if self.arm else 0.0,
            armOmega=self.arm.omega if self.arm else 0.0,
            ekTotal=w.kineticEnergy(),
            epTotal=w.potentialEnergy(self.refY),
            released=self.released,
        )
        s.eTotal = s.ekTotal + s.epTotal
        self.samples.append(s)
        if self._initial is None:
            self._initial = s
        return s

    def mark(self, label: str) -> Event:
        """Zaznacza zdarzenie w historii (zwolnienie liny, start, lądowanie).
        Zapamiętuje stan pocisku dokładnie w tej chwili - to z tego liczy się
        potem prędkość wylotowa i energię przekazaną."""
        b = self.body
        e = Event(t=self.world.time, label=label,
                  speed=b.vel.length(), ek=b.kineticEnergy(),
                  armAngle=self.arm.rot if self.arm else 0.0)
        self.events.append(e)
        if "zwolnien" in label.lower() or "release" in label.lower():
            self.released = True
        return e

    # ---- wyniki ---------------------------------------------------------
    @property
    def storedEnergy(self) -> float:
        """Energia zgromadzona w układzie na starcie [J].

        Liczona jako całkowita energia mechaniczna pierwszej próbki. Przy
        starcie ze spoczynku to czysta energia potencjalna - u trebusza
        po prostu m*g*h podniesionej przeciwwagi (plus ramię i pozostałe
        elementy nad poziomem odniesienia)."""
        return self._initial.eTotal if self._initial else 0.0

    @property
    def launch(self) -> Optional[Event]:
        """Zdarzenie zwolnienia (pierwsze oznaczone jako release)."""
        for e in self.events:
            if "zwolnien" in e.label.lower() or "release" in e.label.lower():
                return e
        return None

    def peakSpeed(self) -> Tuple[float, float]:
        """(maksymalna prędkość, czas jej wystąpienia)."""
        if not self.samples:
            return 0.0, 0.0
        s = max(self.samples, key=lambda p: p.speed)
        return s.speed, s.t

    def maxHeight(self) -> float:
        return max((s.y for s in self.samples), default=0.0)

    def energyDrift(self) -> float:
        """Względna zmiana energii mechanicznej układu [%].

        MIARA JAKOŚCI SYMULACJI: idealny solver zachowuje energię, więc dryf
        bliski zeru znaczy, że podkroków jest dosyć. Dryf dodatni = solver sam
        sobie dodaje energii (za mało podkroków), ujemny = tłumienie.

        UWAGA na interpretację: strata energii NIE zawsze oznacza błąd
        solvera. Więz jednostronny (lina) napinający się z luzu to zderzenie
        NIESPRĘŻYSTE i traci energię z fizycznych powodów. Sprawdzone
        na scenach testowych: układ z samych więzów dwustronnych (wahadło
        z prętów) daje dryf 0.000 % niezależnie od liczby podkroków,
        a trebusz z linami traci ok. 18 % niezależnie od liczby podkroków -
        czyli to strata fizyczna, a nie numeryczna.

        Liczone TYLKO DO chwili zwolnienia więzu - po zwolnieniu układ
        przestaje być zachowawczy z definicji (pocisk odlatuje, lina zostaje,
        pojawia się kontakt z gruntem), więc dalszy dryf nic nie mówi
        o jakości solvera."""
        if len(self.samples) < 2 or self.storedEnergy == 0.0:
            return 0.0
        ev = self.launch
        window = ([s for s in self.samples if s.t <= ev.t] if ev
                  else self.samples)
        if len(window) < 2:
            return 0.0
        return 100.0 * (window[-1].eTotal - self.storedEnergy) / abs(self.storedEnergy)

    def efficiency(self) -> float:
        """Sprawność maszyny: jaka część zgromadzonej energii trafiła
        do pocisku w chwili zwolnienia [%]."""
        ev = self.launch
        if ev is None or self.storedEnergy == 0.0:
            return 0.0
        return 100.0 * ev.ek / abs(self.storedEnergy)

    def ballisticRange(self) -> float:
        """Teoretyczny zasięg rzutu ukośnego z chwili zwolnienia [m].

        Liczony analitycznie z v0, kąta i wysokości - niezależnie od tego,
        czy symulacja doleciała do końca. Pozwala porównywać nastawy maszyny
        bez czekania na lądowanie."""
        ev = self.launch
        if ev is None:
            return 0.0
        s = min(self.samples, key=lambda p: abs(p.t - ev.t))
        g = -self.world.gravity.y
        disc = s.vy * s.vy + 2.0 * g * max(s.y - self.refY, 0.0)
        if disc < 0.0:
            return 0.0
        tFlight = (s.vy + math.sqrt(disc)) / g
        return s.x + s.vx * tFlight

    # ---- serie do wykresów ---------------------------------------------
    def series(self, *fields: str) -> Tuple[List[float], ...]:
        """Zwraca wybrane kolumny jako osobne listy - gotowe pod matplotlib.

            t, ek = analyzer.series("t", "ekBody")
            kat, ek = analyzer.series("armAngle", "ekBody")
        """
        return tuple([getattr(s, f) for s in self.samples] for f in fields)

    def energyVsAngle(self) -> Tuple[List[float], List[float]]:
        """(kąt ramienia w stopniach, energia kinetyczna pocisku [J]).
        To jest ten wykres, o który chodzi przy optymalizacji kąta zwolnienia:
        widać na nim, w którym momencie obrotu pocisk ma najwięcej energii."""
        kat = [math.degrees(s.armAngle) for s in self.samples]
        ek = [s.ekBody for s in self.samples]
        return kat, ek

    # ---- eksport --------------------------------------------------------
    def saveCsv(self, path: str) -> str:
        """Zapisuje całą historię do CSV (Excel, pandas, gnuplot)."""
        if not self.samples:
            return path
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.samples[0])))
            writer.writeheader()
            for s in self.samples:
                writer.writerow(asdict(s))
        return path

    def savePlot(self, path: str) -> Optional[str]:
        """Wykresy (jeśli jest matplotlib): Ek(t), Ek(kąt), bilans energii.
        Brak matplotlib nie jest błędem - dane i tak są w CSV."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("[analyzer] brak matplotlib - pomijam wykres, dane są w CSV")
            return None

        t, ek, ekTot, epTot, eTot = self.series(
            "t", "ekBody", "ekTotal", "epTotal", "eTotal")
        kat, ekk = self.energyVsAngle()

        fig, ax = plt.subplots(1, 3, figsize=(15, 4))
        ax[0].plot(t, ek)
        ax[0].set_xlabel("czas [s]")
        ax[0].set_ylabel("Ek pocisku [J]")
        ax[0].set_title("Energia kinetyczna pocisku")

        ax[1].plot(kat, ekk)
        ax[1].set_xlabel("kąt ramienia [stopnie]")
        ax[1].set_ylabel("Ek pocisku [J]")
        ax[1].set_title("Ek w funkcji kąta ramienia")

        ax[2].plot(t, ekTot, label="Ek układu")
        ax[2].plot(t, epTot, label="Ep układu")
        ax[2].plot(t, eTot, label="E całkowita")
        ax[2].set_xlabel("czas [s]")
        ax[2].set_ylabel("energia [J]")
        ax[2].set_title("Bilans energii")
        ax[2].legend()

        for a in ax:
            for e in self.events:
                a.axvline(e.t, color="r", ls="--", lw=0.8) if a is not ax[1] else None

        fig.tight_layout()
        fig.savefig(path, dpi=110)
        plt.close(fig)
        return path

    # ---- podsumowanie ---------------------------------------------------
    def summary(self) -> str:
        vmax, tmax = self.peakSpeed()
        ev = self.launch
        lines = [
            "=" * 62,
            f" ANALIZA: ciało '{self.body.name or type(self.body).__name__}'"
            f"  (masa {self.body.mass:.3g} kg)",
            "=" * 62,
            f" energia zgromadzona na starcie : {self.storedEnergy:10.2f} J",
            f" maks. prędkość                 : {vmax:10.2f} m/s  (t = {tmax:.2f} s)",
            f" maks. wysokość                 : {self.maxHeight():10.2f} m",
        ]
        if ev:
            lines += [
                f" --- zwolnienie ({ev.label}) w t = {ev.t:.2f} s ---",
                f" prędkość wylotowa              : {ev.speed:10.2f} m/s",
                f" energia przekazana pociskowi   : {ev.ek:10.2f} J",
                f" sprawność maszyny              : {self.efficiency():10.2f} %",
                f" kąt ramienia przy zwolnieniu   : {math.degrees(ev.armAngle):10.2f} st.",
                f" zasięg (rzut ukośny)           : {self.ballisticRange():10.2f} m",
            ]
        else:
            lines.append(" (jeszcze nie zwolniono)")
        lines += [
            f" dryf energii układu            : {self.energyDrift():+10.3f} %",
            f" liczba próbek                  : {len(self.samples):10d}",
            "=" * 62,
        ]
        return "\n".join(lines)
