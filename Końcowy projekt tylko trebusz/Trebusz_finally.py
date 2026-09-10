"""
Trebusz_finally.py -- WARSTWA 5: program główny.

To jedyny plik, który importuje pygame. Fizyka (Vector2/Body/Joint/World)
o grafice nie wie, więc zamiana biblioteki graficznej albo policzenie
symulacji bez okna dotyka wyłącznie tego pliku.

PODZIAŁ NA PLIKI - dlaczego tak
    Vector2_finally   algebra           <- nie zależy od niczego
    Body_finally      bryła + wzory XPBD <- Vector2
    Joint_finally     złącza            <- Vector2, Body
    World_finally     solver + klocki   <- Body, Joint
    Trebusz_finally   okno, scena, pętla <- wszystko powyżej

    Zależności idą TYLKO W DÓŁ - żaden plik nie importuje niczego z pliku
    wyższego. To jest praktyczne kryterium dobrego podziału: każdą warstwę
    da się przetestować bez tych nad nią (SOLID: S - jedna odpowiedzialność,
    D - warstwa niższa nie wie o wyższej).

STEROWANIE
    SPACJA  pauza
    F       zwolnij pocisk (przecięcie procy - patrz release_projectile)
    C       zwolnij przeciwwagę
    R       restart sceny
    ESC     wyjście
"""

import math
import pygame

from Vector2_finally import Vec2
from Body_finally import Beam, PointMass, MAX_COORD
from Joint_finally import RopeJoint, RevoluteJoint, FixedJoint
from World_finally import World

pygame.init()

# =============================================================================
# %% 1. OKNO I KAMERA
# =============================================================================

screen_width, screen_height = 3200, 2000
win = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Trebusz - złącza XPBD 2D")
clock = pygame.time.Clock()

simMinWidth = 6.0                       # ile metrów mieści się w oknie
cScale = min(screen_width, screen_height) / simMinWidth


def cX(x: float) -> int:
    return int(screen_width * 0.5 + x * cScale)


def cY(y: float) -> int:
    return int(screen_height * 0.88 - y * cScale)


# =============================================================================
# %% 2. PARAMETRY TREBUSZA
# =============================================================================
# Wszystkie wymiary maszyny w JEDNYM miejscu. Scena poniżej liczy z nich
# wszystkie współrzędne, więc zmiana długości ramienia czy wysokości masztu
# nie wymaga poprawiania ani jednej liczby w setup_scene.
#
# Układ odniesienia: x = 0 w osi masztu, y = 0 na poziomie gruntu.

class TrebuchetParams:
    """Parametry konstrukcyjne trebusza. Zmieniaj TUTAJ, nie w scenie."""

    # --- podstawa (belka wmurowana w grunt) ---
    baseWidth = 2.0
    baseHeight = 0.10
    baseDensity = 0.0            # 0 -> masa 0 -> ciało nieruchome

    # --- maszt: pionowa belka od podstawy do osi obrotu ---
    mastHeight = 2.20            # wysokość osi obrotu nad gruntem
    mastThickness = 0.12
    mastDensity = 25.0

    # --- zastrzał: ukośna belka usztywniająca maszt ---
    braceFootX = -0.8            # gdzie stoi na podstawie
    braceTopY = 1.60             # na jakiej wysokości łapie maszt
    braceThickness = 0.09
    braceDensity = 25.0

    # --- ramię miotające ---
    armLength = 2.0              # CAŁA długość ramienia
    armPivot = 0.25              # oś w 1/4 długości -> proporcja ramion 1:3
    armThickness = 0.12
    armDensity = 120.0           # ciężkie ramię: lekkie stawałoby pionowo
    armMinAngle = -3.0           # ogranicznik wychyłu [rad]
    armMaxAngle = 3.0
    armDamping = 0.5             # wygaszanie kołysania w osi

    # --- przeciwwaga (na krótszym ramieniu) ---
    counterMass = 100.0
    counterRadius = 0.18
    counterRopeLength = 1.2  # długość liny przeciwwagi
    # UWAGA - to jest najczulszy parametr całej maszyny. Przeciwwaga zwisa
    # pionowo, więc ta długość to WPROST wysokość, z jakiej spada 100 kg.
    # Każde 10 cm to 98 J energii wejściowej (m*g*h), a maszyna oddaje
    # pociskowi kilkanaście procent z tego. Zmierzone v_max pocisku:
    #     0.30 m -> 16.1 m/s      0.50 m -> 13.4 m/s      0.80 m -> 9.0 m/s
    # W pierwotnej wersji sceny przeciwwaga wisiała UKOŚNIE: lina miała 0.5 m,
    # ale w pionie dzieliło ją od ramienia tylko 0.3 m. Wyprostowanie zwisu
    # przy zachowaniu długości liny obniżyło masę o 20 cm i zabrało 30 % mocy.
    counterNodes = 3             # z ilu ogniw zrobiona jest ta lina
    counterNodeMass = 1.0        # reguła: >= counterMass / 100

    # --- pocisk (na dłuższym ramieniu, na procy) ---
    projectileMass = 1.0
    projectileRadius = 0.08
    slingLength = 1           # długość procy
    slingAngleDeg = 20.0         # odchylenie procy od pionu na starcie
    slingNodes = 5
    slingNodeMass = 0.1          # reguła: >= projectileMass / 100

    # --- właściwości pochodne: liczone z powyższych, nie wpisujemy ręcznie ---
    @property
    def pivot(self) -> Vec2:
        """Punkt osi obrotu ramienia = szczyt masztu."""
        return Vec2(0.0, self.mastHeight)

    @property
    def armCenterOffset(self) -> float:
        """O ile środek belki ramienia jest przesunięty względem osi.

        Oś ma leżeć w armPivot * armLength od LEWEGO końca, a Beam liczy
        wszystko od swojego środka, czyli od 0.5 * armLength. Różnica:
            0.5*L - armPivot*L = (0.5 - armPivot) * L
        Dla armPivot = 0.25 wychodzi +0.25 * L, czyli środek masy jest
        przesunięty w stronę długiego ramienia - i o to chodzi."""
        return (0.5 - self.armPivot) * self.armLength


params = TrebuchetParams()

# =============================================================================
# %% 3. ŚWIAT
# =============================================================================

world = World(gravity=Vec2(0.0, -9.81), dt=1.0 / 60.0,
              numSubSteps=40,        # POKRĘTŁO nr 2 (sztywność wszystkich więzów)
              numIterations=1)       # POKRĘTŁO nr 3

# Uchwyty do części maszyny - ustawiane w setup_scene, używane przez klawisze.
# Dzięki nim wiadomo, KTÓRE ciało zwolnić po naciśnięciu F.
arm = None
projectile = None
counterweight = None


# =============================================================================
# %% 4. SCENA - BUDOWA TREBUSZA Z KLOCKÓW
# =============================================================================

def setup_scene() -> None:
    """Buduje trebusz wyłącznie na podstawie params - żadnych "magicznych"
    współrzędnych.

    Kolejność montażu (jak przy prawdziwej konstrukcji):
        1. podstawa            Beam(density=0)   - fundament, nieruchomy
        2. maszt               FixedJoint        - przyspawany do podstawy
        3. zastrzał            2 x FixedJoint    - usztywnia maszt do ramy
        4. ramię miotające     RevoluteJoint     - oś obrotu w szczycie masztu
        5. przeciwwaga         lina z ogniw      - na krótszym ramieniu
        6. pocisk na procy     lina z ogniw      - na dłuższym ramieniu
    """
    global arm, projectile, counterweight
    p = params
    world.clear()

    # --- 1. PODSTAWA -----------------------------------------------------
    # density = 0 -> masa 0 -> invMass = invInertia = 0 -> ciało nieruchome
    base = world.addBeam(0.0, p.baseHeight / 2,
                         p.baseWidth, p.baseHeight,
                         density=p.baseDensity, color=(120, 122, 132))

    # --- 2. MASZT (pionowa belka do osi obrotu) --------------------------
    mastFoot = Vec2(0.0, p.baseHeight)
    mast = world.addBeamBetween(mastFoot, p.pivot, p.mastThickness,
                                density=p.mastDensity, color=(176, 138, 84))
    world.connectFixed(base, mast, mastFoot)              # SPAW do podstawy

    # --- 3. ZASTRZAŁ (ukośna belka usztywniająca) ------------------------
    braceFoot = Vec2(p.braceFootX, p.baseHeight)
    braceTop = Vec2(0.0, p.braceTopY)
    brace = world.addBeamBetween(braceFoot, braceTop, p.braceThickness,
                                 density=p.braceDensity, color=(176, 138, 84))
    world.connectFixed(base, brace, braceFoot)            # SPAW do podstawy
    world.connectFixed(mast, brace, braceTop)             # SPAW do masztu
    # Dwa spawy + belka = trójkąt. Trójkąt jest figurą niedeformowalną,
    # więc maszt nie może się położyć nawet pod obciążeniem 100 kg.

    # --- 4. RAMIĘ MIOTAJĄCE na ZAWIASIE ---------------------------------
    # Środek belki leży armCenterOffset na prawo od osi, więc oś wypada
    # dokładnie w armPivot * armLength od lewego końca.
    arm = world.addBeam(p.armCenterOffset, p.mastHeight,
                        p.armLength, p.armThickness,
                        density=p.armDensity)
    world.connectRevolute(mast, arm, p.pivot,
                          minAngle=p.armMinAngle,     # ogranicznik wychyłu
                          maxAngle=p.armMaxAngle,
                          damping=p.armDamping)       # wygaszanie kołysania

    shortTip = arm.end(-1.0)     # koniec KRÓTKIEGO ramienia (przeciwwaga)
    longTip = arm.end(1.0)       # koniec DŁUGIEGO ramienia (proca)

    # --- 5. PRZECIWWAGA na krótkiej linie -------------------------------
    # zwisa pionowo w dół od końca krótkiego ramienia
    cwPos = shortTip.clone().add(Vec2(0.0, -p.counterRopeLength))
    counterweight = world.addPointMass(cwPos.x, cwPos.y, p.counterMass,
                                       p.counterRadius, color=(205, 70, 70))
    world.connectRopeChain(arm, shortTip, counterweight, cwPos,
                           numNodes=p.counterNodes,
                           nodeMass=p.counterNodeMass)

    # --- 6. POCISK na procy ---------------------------------------------
    # Proca odchylona od pionu o slingAngleDeg w stronę masztu - tak jak
    # w naładowanym trebuszu, gdzie pocisk leży bliżej podstawy niż koniec
    # ramienia. Kierunek liczony z kąta, więc zmiana długości ramienia
    # przesuwa pocisk automatycznie.
    a = math.radians(p.slingAngleDeg)
    slingDir = Vec2(-math.sin(a), -math.cos(a))          # w dół, lekko w lewo
    projPos = longTip.clone().add(slingDir, p.slingLength)
    projectile = world.addPointMass(projPos.x, projPos.y, p.projectileMass,
                                    p.projectileRadius, color=(90, 200, 255))
    world.connectRopeChain(arm, longTip, projectile, projPos,
                           numNodes=p.slingNodes,
                           nodeMass=p.slingNodeMass)


# =============================================================================
# %% 5. ZWALNIANIE (SPUST)
# =============================================================================

def release_projectile() -> None:
    """Zwolnienie pocisku - odpowiednik przecięcia procy.

    Całe działanie to jedna linijka: world.releaseBody(projectile) wyłącza
    wszystkie więzy, w których występuje pocisk (czyli ostatnie ogniwo procy).
    Od tej chwili działa na niego tylko grawitacja - czysty rzut ukośny.
    Lina zostaje na ramieniu i dalej faluje, bo jej pozostałe ogniwa nie
    zostały ruszone."""
    n = world.releaseBody(projectile)
    if n:
        v = projectile.vel
        print(f"[F] zwolniono pocisk: v = {v.length():.2f} m/s, "
              f"kąt = {math.degrees(math.atan2(v.y, v.x)):+.1f} st., "
              f"Ek = {projectile.kineticEnergy():.1f} J")


def release_counterweight() -> None:
    """To samo dla przeciwwagi - żeby zobaczyć, jak maszyna zachowa się
    po odczepieniu napędu."""
    if world.releaseBody(counterweight):
        print("[C] zwolniono przeciwwagę")


# =============================================================================
# %% 6. RYSOWANIE
# =============================================================================

SHOW_FORCES = False        # True -> podpisy z siłą i wydłużeniem przy złączach
fontSmall = pygame.font.SysFont("consolas", 24)


def draw_forces() -> None:
    """Podpisy przy złączach: siła więzu i wydłużenie.

    j.force        siła w niutonach (lambda/dt^2 z applyLinearCorrection);
                   format {:5.0f} rezerwuje 5 znaków, żeby liczby nie skakały
    j.elongation   wydłużenie w metrach, mnożone przez 1000 -> milimetry;
                   {:+.1f} wymusza znak, więc od razu widać, czy więz jest
                   rozciągnięty czy ściśnięty
    mx, my         środek odcinka między punktami zaczepienia, przesunięty
                   o kilka pikseli, żeby tekst nie leżał NA złączu

    Diagnostyka: jeśli siły są rzędu ciężaru tego, co wisi poniżej,
    a wydłużenia to ułamki milimetra - solver zbiega poprawnie."""
    for j in world.joints:
        j.updateGlobalFrames()
        mx = cX(0.5 * (j.globalPos0.x + j.globalPos1.x)) + 10
        my = cY(0.5 * (j.globalPos0.y + j.globalPos1.y)) - 8
        win.blit(fontSmall.render(
            f"{j.force:5.0f} N  {j.elongation * 1000:+.1f} mm",
            True, (200, 160, 160)), (mx, my))


def draw() -> None:
    win.fill((28, 30, 36))

    # grunt
    pygame.draw.line(win, (95, 115, 85), (0, cY(0.0)), (screen_width, cY(0.0)), 4)

    # złącza: linki jako odcinki, zawiasy jako kółka, spawy jako pierścienie
    for j in world.joints:
        j.updateGlobalFrames()
        if not (j.globalPos0.isFinite() and j.globalPos1.isFinite()):
            continue
        p0 = (cX(j.globalPos0.x), cY(j.globalPos0.y))
        if isinstance(j, RopeJoint):
            # zwolniona lina rysowana na ciemno - widać, co już nie działa
            color = (110, 80, 80) if j.disabled else (238, 238, 238)
            pygame.draw.line(win, color, p0,
                             (cX(j.globalPos1.x), cY(j.globalPos1.y)), 3)
        elif isinstance(j, RevoluteJoint):
            pygame.draw.circle(win, (255, 255, 255), p0, 14)
            pygame.draw.circle(win, (40, 40, 45), p0, 14, 3)
        elif isinstance(j, FixedJoint):
            pygame.draw.circle(win, (235, 90, 90), p0, 11, 3)

    # ciała
    for b in world.bodies:
        # bezpiecznik rysowania: ciało, które uciekło w nieskończoność,
        # pomijamy - inaczej pygame dostaje współrzędne spoza zakresu int
        # i rysuje "spłaszczone" wielokąty
        if not b.pos.isFinite() or abs(b.pos.x) > MAX_COORD or abs(b.pos.y) > MAX_COORD:
            continue
        if isinstance(b, Beam):
            pts = [(cX(v.x), cY(v.y)) for v in b.corners()]
            pygame.draw.polygon(win, b.color, pts)
            pygame.draw.polygon(win, (35, 35, 40), pts, 3)
        elif isinstance(b, PointMass):
            pygame.draw.circle(win, b.color, (cX(b.pos.x), cY(b.pos.y)),
                               max(int(b.radius * cScale), 5))

    if SHOW_FORCES:
        draw_forces()

    win.blit(fontSmall.render(
        "SPACJA pauza | F zwolnij pocisk | C zwolnij przeciwwagę | R restart",
        True, (200, 200, 210)), (20, 20))

    pygame.display.update()


# =============================================================================
# %% 7. PĘTLA GŁÓWNA
# =============================================================================

setup_scene()

paused = False
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_SPACE:
                paused = not paused
            elif event.key == pygame.K_f:          # <-- SPUST
                release_projectile()
            elif event.key == pygame.K_c:
                release_counterweight()
            elif event.key == pygame.K_r:
                setup_scene()

    if not paused:
        world.simulate()
    draw()
    clock.tick(60)

pygame.quit()
