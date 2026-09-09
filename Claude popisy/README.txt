# Symulator brył sztywnych 2D (XPBD)

Silnik fizyczny do budowania konstrukcji „z klocków" — prostokątów, kół i mas
punktowych łączonych złączami sztywnymi i ruchomymi — wraz z analizą
kinematyki i energii. Domyślna scena to trebusz.

## Uruchomienie

```bash
python main.py
```

| klawisz | działanie |
|---|---|
| SPACJA | zwolnij procę (pocisk odlatuje) |
| C | zwolnij przeciwwagę |
| 1 / 2 | scena: trebusz / maszyny |
| A | automatyczne zwolnienie przy zadanym kącie ramienia |
| R | restart sceny |
| P | pauza |
| F | podgląd ramek zaczepienia złączy |
| S | zapis `analiza_*.csv`, `analiza_*.png` i podsumowania |
| ESC | wyjście |

## Struktura

Zależności idą wyłącznie w dół — żaden moduł nie importuje niczego z wyższej
warstwy.

```
pbd2d/
    vector2.py    algebra wektorowa                     (nie zależy od niczego)
    config.py     parametry solvera i świata
    xpbd.py       dwa wzory korekcyjne                  <- vector2
    bodies.py     Body, Beam, Disk, PointMass, CompositeBeam
    joints.py     Joint + 6 typów złączy                <- bodies, xpbd
    world.py      SOLVER: krok czasowy, zwalnianie więzów
    builder.py    FABRYKA scen (płynne API, rejestr nazw)
    analyzer.py   pomiary, bilans energii, CSV, wykresy
    renderer.py   rysowanie                             (jedyny plik z pygame)
scenes/
    trebuchet.py  trebusz z parametrami w dataclass
    machines.py   demo nowych złączy i kształtów
main.py           pętla, sterowanie, spięcie warstw
```

Silnika można używać bez pygame — `renderer.py` nie jest importowany
w `pbd2d/__init__.py`, więc obliczenia wsadowe (np. skan parametrów) działają
w środowisku bez grafiki.

## Warstwy: co gdzie zmieniać

| chcę zmienić | plik |
|---|---|
| algorytm solvera, wzory korekcji | `xpbd.py` |
| sztywność więzów, bezpieczniki | `config.py` |
| nowy kształt ciała | `bodies.py` + wpis w `renderer.bodyDrawers` |
| nowy typ złącza | `joints.py` + wpis w `renderer.jointDrawers` |
| nową maszynę | nowy plik w `scenes/` |
| co jest mierzone | `analyzer.py` |
| wygląd, sterowanie | `renderer.py`, `main.py` |

## Jak dodać nowy kształt

Wystarczy policzyć masę i moment bezwładności w konstruktorze — reszta
(więzy, korekty, energia) działa bez zmian, bo solver widzi tylko `Body`:

```python
class Triangle(Body):
    def __init__(self, pos, a, h, density=1.0, **kw):
        m = density * 0.5 * a * h
        I = m * (a*a + h*h) / 36.0          # względem środka masy!
        super().__init__(pos, mass=m, inertia=I, **kw)
```

Potem jedna linijka w rendererze:

```python
renderer.bodyDrawers[Triangle] = my_draw_function
```

**Moment bezwładności zawsze względem środka masy**, nigdy względem osi
złącza. Wpływ położenia osi wchodzi sam, przez człon `(r × n)²/I`
w uogólnionej masie odwrotnej — to twierdzenie Steinera liczone w locie.
Z tablic bierzemy więc `mL²/12` (pręt względem środka), nie `mL²/3`
(względem końca). Wyjątek: ciało złożone z kilku kawałków traktowane jako
jedna bryła — patrz `CompositeBeam`.

## Jak dodać nowe złącze

Złożyć gotowe klocki z klasy `Joint`:

```python
class MyJoint(Joint):
    def solvePosition(self):
        self.attach(0.0)                    # punkty razem
    def solveOrientation(self):
        self.limitAngle(-0.3, 0.3)          # zakres kąta
```

Dostępne klocki: `attach`, `alignAngle`, `limitAngle`, `restrictToAxis`,
`dampLinear`, `dampAngular`. Solver nie wymaga żadnych zmian.

## Strojenie sztywności lin

Więz z `compliance = 0` jest formalnie nierozciągliwy, ale solver jest typu
Gauss-Seidel i jego zbieżność psuje się przy skrajnym stosunku mas.
Zmierzone (ładunek 100 kg, 5 ogniw, 40 podkroków):

| masa ogniwa | rozciągnięcie liny |
|---|---|
| 0,001 kg | 169 % |
| 0,01 kg | 16 % |
| 0,1 kg | 1,2 % |
| 0,5 kg | 0,17 % |
| 2,0 kg | 0,04 % |

Pokrętła w kolejności skuteczności:

1. `nodeMass` w `SceneBuilder.ropeChain` — reguła: **masa ogniwa ≥ ładunek/100**.
   `None` dobiera automatycznie (ładunek/50); za małą wartość builder podnosi
   z komunikatem.
2. `SolverConfig.numSubSteps` — błąd maleje mniej więcej jak 1/n², koszt rośnie liniowo.
3. `SolverConfig.numIterations` — słabsze niż podkroki przy tym samym koszcie.
4. `numNodes` — mniej ogniw = sztywniej, więcej = ładniejszy zwis.

`compliance > 0` to **celowa sprężystość** (patrz `SpringJoint`, gdzie
`compliance = 1/k`), a nie lekarstwo na gumujące się liny.

## Analiza

`Analyzer` rejestruje się jako obserwator świata — solver o nim nie wie:

```python
analyzer = Analyzer(world, body=builder["pocisk"], arm=builder["ramie"])
world.addObserver(analyzer)
...
analyzer.mark("zwolnienie: proca")     # zaznaczenie zdarzenia
print(analyzer.summary())
analyzer.saveCsv("analiza.csv")
analyzer.savePlot("analiza.png")       # pomija się, gdy brak matplotlib
kat, ek = analyzer.energyVsAngle()     # dane pod własny wykres
```

Dostępne wielkości: `storedEnergy` (energia zgromadzona na starcie),
`efficiency()` (jaka jej część trafiła do pocisku), `peakSpeed()`,
`maxHeight()`, `ballisticRange()` (zasięg liczony analitycznie z chwili
zwolnienia), `energyDrift()`.

**Interpretacja dryfu energii.** Strata energii nie zawsze oznacza błąd
solvera. Sprawdzone na scenach testowych: wahadło z samych więzów
dwustronnych daje dryf 0,000 % niezależnie od liczby podkroków, a trebusz
z linami traci ~18 % również niezależnie od liczby podkroków — bo lina
napinająca się z luzu to zderzenie niesprężyste i traci energię z powodów
fizycznych, nie numerycznych.

## Skan parametrów bez grafiki

Ponieważ scena jest opisana dataclassą, badanie wpływu dowolnego parametru
na zasięg to zwykła pętla:

```python
from pbd2d import World, WorldConfig, SolverConfig, Analyzer, Vec2
from scenes import trebuchet

for sling in (1.2, 1.5, 1.8, 2.1):
    p = trebuchet.TrebuchetParams(slingLength=sling)
    world = World(WorldConfig(groundY=0.0))
    b = trebuchet.build(world, p)
    a = Analyzer(world, b["pocisk"], b["ramie"]); world.addObserver(a)
    for _ in range(400):
        world.simulate()
        if a.launch is None and b["ramie"].rot < p.releaseAngle:
            world.release("proca"); a.mark("zwolnienie: proca")
    print(sling, a.ballisticRange())
```
