"""
analiza_wykresy.py -- wczytuje CSV zapisany przez Analyzer i pokazuje wyniki.

URUCHOMIENIE
    python analiza_wykresy.py                      # bierze analiza_trebusz.csv
    python analiza_wykresy.py plik.csv             # konkretny plik
    python analiza_wykresy.py plik.csv --save w.png  # zapis zamiast okna
    python analiza_wykresy.py a.csv b.csv          # porównanie kilku przebiegów

CO ROBI
    1. wczytuje plik (moduł csv - bez pandas, żeby nie dokładać zależności)
    2. liczy wielkości charakterystyczne i wypisuje raport w konsoli
    3. rysuje 6 wykresów w jednym oknie

DLACZEGO OSOBNY PROGRAM
    Analiza po fakcie nie ma nic wspólnego z symulacją: czyta plik i rysuje.
    Trzymanie tego poza pakietem pbd2d oznacza, że można analizować dane
    z dowolnego przebiegu (także sprzed tygodnia) bez uruchamiania fizyki.

KOLUMNY W CSV (zapisywane przez pbd2d.analyzer.Sample)
    t, x, y, vx, vy, speed, angleDeg, ekBody, epBody,
    armAngle, armOmega, ekTotal, epTotal, eTotal, released
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


# =============================================================================
# %% 1. WCZYTANIE DANYCH
# =============================================================================

def load(path: str) -> Dict[str, List[float]]:
    """Wczytuje CSV do słownika kolumn: {"t": [...], "speed": [...], ...}.

    Kolumna 'released' jest tekstem 'True'/'False', więc zamieniamy ją na 0/1 -
    dzięki temu wszystkie kolumny są liczbowe i można je rysować bez wyjątków.
    """
    cols: Dict[str, List[float]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key, value in row.items():
                if key is None:
                    continue
                if value in ("True", "False"):
                    number = 1.0 if value == "True" else 0.0
                else:
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        continue
                cols.setdefault(key, []).append(number)
    if not cols:
        raise ValueError(f"Plik {path} nie zawiera danych liczbowych")
    return cols


# =============================================================================
# %% 2. WIELKOŚCI CHARAKTERYSTYCZNE
# =============================================================================

@dataclass
class Report:
    """Komplet liczb wyciągniętych z jednego przebiegu."""
    name: str = ""
    duration: float = 0.0
    samples: int = 0

    storedEnergy: float = 0.0      # energia zgromadzona na starcie [J]
    mass: float = 0.0              # masa śledzonego ciała [kg] (z Ek i v)

    releaseTime: Optional[float] = None
    releaseSpeed: float = 0.0
    releaseAngleDeg: float = 0.0   # kierunek lotu [stopnie]
    releaseArmDeg: float = 0.0     # kąt ramienia w chwili zwolnienia
    releaseEk: float = 0.0
    releaseHeight: float = 0.0

    peakSpeed: float = 0.0
    peakSpeedTime: float = 0.0
    peakEk: float = 0.0
    peakEkArmDeg: float = 0.0      # przy jakim kącie ramienia Ek jest maks.
    peakOmega: float = 0.0

    maxHeight: float = 0.0
    landingX: Optional[float] = None
    flightTime: Optional[float] = None
    ballisticRange: float = 0.0

    efficiency: float = 0.0        # ile % energii zgromadzonej trafiło do pocisku
    energyDrift: float = 0.0       # dryf energii układu do chwili zwolnienia [%]


def analyze(cols: Dict[str, List[float]], name: str = "",
            g: float = 9.81) -> Report:
    """Liczy wszystkie wielkości charakterystyczne z wczytanych kolumn."""
    t = cols["t"]
    r = Report(name=name, duration=t[-1], samples=len(t))

    speed = cols["speed"]
    ek = cols["ekBody"]
    y = cols["y"]
    x = cols["x"]

    # masa odtworzona z Ek = 1/2 m v^2 - bierzemy próbkę o największej
    # prędkości, żeby uniknąć dzielenia przez zero na starcie
    iFast = max(range(len(speed)), key=lambda i: speed[i])
    if speed[iFast] > 0.0:
        r.mass = 2.0 * ek[iFast] / (speed[iFast] ** 2)

    r.storedEnergy = cols["eTotal"][0]

    # --- chwila zwolnienia: pierwsza próbka z released == 1 ---------------
    iRel = next((i for i, v in enumerate(cols.get("released", [])) if v > 0.5),
                None)
    if iRel is not None:
        r.releaseTime = t[iRel]
        r.releaseSpeed = speed[iRel]
        r.releaseAngleDeg = cols["angleDeg"][iRel]
        r.releaseArmDeg = math.degrees(cols["armAngle"][iRel])
        r.releaseEk = ek[iRel]
        r.releaseHeight = y[iRel]
        if r.storedEnergy:
            r.efficiency = 100.0 * r.releaseEk / abs(r.storedEnergy)

        # zasięg z rzutu ukośnego - liczony analitycznie ze stanu w chwili
        # zwolnienia, niezależnie od tego, czy symulacja doleciała do końca
        vx, vy = cols["vx"][iRel], cols["vy"][iRel]
        disc = vy * vy + 2.0 * g * max(y[iRel], 0.0)
        if disc >= 0.0:
            tf = (vy + math.sqrt(disc)) / g
            r.ballisticRange = x[iRel] + vx * tf

        # lądowanie: pierwszy moment PO zwolnieniu, gdy pocisk schodzi
        # do poziomu startu i przestaje opadać
        y0 = y[iRel]
        for i in range(iRel + 1, len(t)):
            if y[i] <= y[0] + 1e-6 and cols["vy"][i] <= 0.0:
                r.landingX = x[i]
                r.flightTime = t[i] - r.releaseTime
                break

        # dryf energii liczymy tylko do zwolnienia - potem układ przestaje
        # być zachowawczy (pocisk odlatuje, lina zostaje)
        if r.storedEnergy:
            r.energyDrift = 100.0 * (cols["eTotal"][iRel] - r.storedEnergy) \
                            / abs(r.storedEnergy)

    # --- ekstrema --------------------------------------------------------
    r.peakSpeed, r.peakSpeedTime = speed[iFast], t[iFast]
    iEk = max(range(len(ek)), key=lambda i: ek[i])
    r.peakEk = ek[iEk]
    r.peakEkArmDeg = math.degrees(cols["armAngle"][iEk])
    r.maxHeight = max(y)
    if "armOmega" in cols:
        r.peakOmega = max(cols["armOmega"], key=abs)
    return r


def printReport(r: Report) -> None:
    """Raport w konsoli. Format kolumnowy, żeby dało się porównywać wzrokiem."""
    line = "=" * 66
    print(line)
    print(f" WYNIKI: {r.name}")
    print(line)
    print(f" czas przebiegu                 : {r.duration:10.2f} s"
          f"   ({r.samples} próbek)")
    print(f" masa śledzonego ciała          : {r.mass:10.3f} kg")
    print(f" energia zgromadzona na starcie : {r.storedEnergy:10.2f} J")
    print("-" * 66)

    if r.releaseTime is None:
        print(" (w tym przebiegu nie zwolniono więzu)")
    else:
        print(f" ZWOLNIENIE w t = {r.releaseTime:.3f} s")
        print(f"   prędkość wylotowa v0         : {r.releaseSpeed:10.2f} m/s")
        print(f"   kąt wylotu                   : {r.releaseAngleDeg:10.2f} st.")
        print(f"   kąt ramienia                 : {r.releaseArmDeg:10.2f} st.")
        print(f"   wysokość zwolnienia          : {r.releaseHeight:10.2f} m")
        print(f"   energia przekazana pociskowi : {r.releaseEk:10.2f} J")
        print(f"   SPRAWNOŚĆ MASZYNY            : {r.efficiency:10.2f} %")
        print("-" * 66)
        print(f" zasięg teoretyczny (rzut ukośny): {r.ballisticRange:9.2f} m")
        if r.landingX is not None:
            print(f" zasięg z symulacji              : {r.landingX:9.2f} m"
                  f"   (lot {r.flightTime:.2f} s)")
        print(f" dryf energii do zwolnienia      : {r.energyDrift:+9.3f} %")

    print("-" * 66)
    print(f" maks. prędkość pocisku         : {r.peakSpeed:10.2f} m/s"
          f"   (t = {r.peakSpeedTime:.2f} s)")
    print(f" maks. energia kinetyczna       : {r.peakEk:10.2f} J"
          f"   (kąt ramienia {r.peakEkArmDeg:.1f} st.)")
    print(f" maks. wysokość                 : {r.maxHeight:10.2f} m")
    print(f" maks. prędkość kątowa ramienia : {r.peakOmega:10.2f} rad/s")

    # najciekawsza obserwacja: czy zwolniono w najlepszym momencie
    if r.releaseTime is not None:
        delta = r.peakEk - r.releaseEk
        if r.peakEk > 0.0 and delta / r.peakEk > 0.02:
            print("-" * 66)
            print(f" UWAGA: pocisk miał maksimum energii ({r.peakEk:.1f} J)"
                  f" przy kącie {r.peakEkArmDeg:.1f} st.,")
            print(f" a zwolniono go przy {r.releaseArmDeg:.1f} st."
                  f" z energią {r.releaseEk:.1f} J.")
            print(f" Zmiana kąta zwolnienia może dać do"
                  f" {100.0 * delta / max(r.releaseEk, 1e-9):.0f} %"
                  f" więcej energii wylotowej.")
    print(line)


# =============================================================================
# %% 3. WYKRESY
# =============================================================================

def plot(datasets: List[Dict[str, List[float]]], reports: List[Report],
         savePath: Optional[str] = None) -> None:
    """Sześć wykresów w jednym oknie.

    1. Ek pocisku w czasie          - kiedy maszyna oddaje energię
    2. Ek pocisku od kąta ramienia  - GŁÓWNY wykres optymalizacyjny:
                                      widać, przy jakim kącie zwolnić
    3. tor lotu y(x)                - trajektoria z zaznaczonym zwolnieniem
    4. prędkość i kąt wylotu w czasie
    5. bilans energii układu        - Ek, Ep i suma (dryf = jakość symulacji)
    6. prędkość kątowa ramienia
    """
    try:
        import matplotlib
        if savePath:
            matplotlib.use("Agg")       # tryb bez okna (zapis do pliku)
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[!] Brak matplotlib - same liczby powyżej.")
        print("    Instalacja:  pip install matplotlib")
        return

    fig, ax = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle("Analiza przebiegu symulacji", fontsize=14)

    for cols, rep in zip(datasets, reports):
        label = rep.name
        t = cols["t"]

        ax[0][0].plot(t, cols["ekBody"], label=label)
        ax[0][1].plot([math.degrees(a) for a in cols["armAngle"]],
                      cols["ekBody"], label=label)
        ax[0][2].plot(cols["x"], cols["y"], label=label)
        ax[1][0].plot(t, cols["speed"], label=label)
        ax[1][1].plot(t, cols["eTotal"], label=f"E całk. {label}")
        ax[1][1].plot(t, cols["ekTotal"], "--", lw=1, label=f"Ek {label}")
        ax[1][1].plot(t, cols["epTotal"], ":", lw=1, label=f"Ep {label}")
        ax[1][2].plot(t, cols["armOmega"], label=label)

        # pionowa kreska w chwili zwolnienia na wykresach czasowych
        if rep.releaseTime is not None:
            for a in (ax[0][0], ax[0][2], ax[1][0], ax[1][1], ax[1][2]):
                if a is ax[0][2]:
                    a.plot([rep.landingX or rep.ballisticRange], [0], "v",
                           ms=8, label="lądowanie" if label == reports[0].name
                           else None)
                else:
                    a.axvline(rep.releaseTime, color="r", ls="--", lw=1)
            # punkt zwolnienia na wykresie Ek(kąt) - tam czas nie jest osią
            ax[0][1].plot([rep.releaseArmDeg], [rep.releaseEk], "ro", ms=7)
            ax[0][1].annotate("zwolnienie",
                              (rep.releaseArmDeg, rep.releaseEk),
                              textcoords="offset points", xytext=(8, 6))

    titles = [
        ("Energia kinetyczna pocisku", "czas [s]", "Ek [J]"),
        ("Ek pocisku od kąta ramienia", "kąt ramienia [st.]", "Ek [J]"),
        ("Tor lotu", "x [m]", "y [m]"),
        ("Prędkość pocisku", "czas [s]", "v [m/s]"),
        ("Bilans energii układu", "czas [s]", "energia [J]"),
        ("Prędkość kątowa ramienia", "czas [s]", "omega [rad/s]"),
    ]
    for a, (title, xl, yl) in zip(ax.flat, titles):
        a.set_title(title)
        a.set_xlabel(xl)
        a.set_ylabel(yl)
        a.grid(alpha=0.3)
        if len(datasets) > 1 or a is ax[1][1]:
            a.legend(fontsize=8)

    ax[0][2].axhline(0.0, color=(0.4, 0.5, 0.4), lw=2)   # grunt
    fig.tight_layout()

    if savePath:
        fig.savefig(savePath, dpi=110)
        print(f"\nWykresy zapisane do: {savePath}")
    else:
        plt.show()          # okno na ekranie


# =============================================================================
# %% 4. PROGRAM GŁÓWNY
# =============================================================================

def main(argv: List[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    savePath = None
    if "--save" in argv:
        i = argv.index("--save")
        savePath = argv[i + 1] if i + 1 < len(argv) else "wykresy.png"

    paths = args or ["analiza_trebusz.csv"]

    datasets, reports = [], []
    for p in paths:
        try:
            cols = load(p)
        except FileNotFoundError:
            print(f"[!] Nie znaleziono pliku: {p}")
            print("    Uruchom najpierw main.py i naciśnij S, żeby zapisać dane.")
            continue
        rep = analyze(cols, name=p.replace(".csv", ""))
        printReport(rep)
        datasets.append(cols)
        reports.append(rep)

    if not datasets:
        return 1

    # porównanie kilku przebiegów - tabelka zbiorcza
    if len(reports) > 1:
        print("\n" + "=" * 66)
        print(" PORÓWNANIE PRZEBIEGÓW")
        print("=" * 66)
        print(f" {'przebieg':<24}{'v0 [m/s]':>10}{'Ek0 [J]':>10}"
              f"{'sprawn. %':>11}{'zasięg [m]':>11}")
        for r in reports:
            print(f" {r.name[:24]:<24}{r.releaseSpeed:>10.2f}{r.releaseEk:>10.1f}"
                  f"{r.efficiency:>11.2f}{r.ballisticRange:>11.2f}")
        print("=" * 66)

    plot(datasets, reports, savePath)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
