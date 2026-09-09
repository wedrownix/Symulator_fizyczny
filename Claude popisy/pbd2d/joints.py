"""
pbd2d/joints.py -- złącza między bryłami.

=============================================================================
 JAK DZIAŁA KLASA Joint
=============================================================================

IDEA
    Złącze nie jest obiektem fizycznym - to REGUŁA, którą solver wymusza na
    dwóch ciałach po tym, jak poleciały swobodnie w kroku integracji.
    Każde złącze odpowiada na dwa pytania:
        "o ile rozjechały się punkty?"  -> solvePosition()
        "o ile rozjechały się kąty?"    -> solveOrientation()
    i zleca poprawkę do modułu xpbd. W tej klasie nie ma ANI JEDNEGO wzoru
    XPBD - jest tylko decyzja, CO ma być poprawione (wzorzec Delegacja).

DWA UKŁADY WSPÓŁRZĘDNYCH (slajd "Attachment Frames")
    Punkt zaczepienia podajesz RAZ, w układzie świata ("zawias w (0, 2.2)").
    Konstruktor od razu przelicza go na współrzędne LOKALNE obu ciał i tylko
    te zapamiętuje:
        localPos  = worldToLocal(anchor)      <- raz, przy montażu
        globalPos = localToWorld(localPos)    <- co podkrok
    Dzięki temu punkt zaczepienia jeździ razem z ciałem za darmo.

DWIE RAMKI, NIE JEDNA
    Każde złącze ma dwie ramki: jedną przyklejoną do body0, drugą do body1.
    Przy montażu leżą w tym samym miejscu i mają ten sam kąt. W trakcie
    symulacji rozjeżdżają się - i właśnie ten rozjazd
    (globalPos1 - globalPos0, globalRot1 - globalRot0) JEST naruszeniem
    więzu. Reszta klasy to różne sposoby mierzenia tego rozjazdu.

WZORZEC: METODA SZABLONOWA
    solve() ma stały scenariusz, a treść kroków dopisują podklasy.
    Klasa bazowa daje im gotowe klocki ze slajdów Müllera:
        attach()      = Attach       trzymaj punkty w zadanej odległości
        alignAngle()  = AlignAxes    trzymaj zadany kąt względny
        limitAngle()  = LimitAngle   trzymaj kąt w przedziale
        restrictToAxis() = RestrictToAxis   pozwól przesuwać się tylko wzdłuż osi
        dampLinear / dampAngular     tłumienie na poziomie prędkości
    Dlatego definicje złączy są jednolinijkowe:
        linka   = attach(length, unilateral=True)
        zawias  = attach(0) [+ limitAngle(...)]
        spaw    = attach(0) + alignAngle(restAngle)
        suwak   = restrictToAxis(...) + alignAngle(...)
    Nowe złącze nie wymaga dotknięcia solvera - to sens tej hierarchii.

ZAWARTOŚĆ PLIKU
    Joint            klasa bazowa (klocki)
    RopeJoint        linka / pręt
    RevoluteJoint    zawias
    FixedJoint       spaw
    --- przykłady rozbudowy ---
    SpringJoint      sprężyna (linka z compliance > 0)
    MotorJoint       napęd obrotowy o zadanej prędkości
    PrismaticJoint   suwak (ruch tylko wzdłuż jednej osi)
"""

from __future__ import annotations
import math
from typing import Optional
from .vector2 import Vec2, normalizeAngle, clamp
from .bodies import Body
from .xpbd import applyLinearCorrection, applyAngularCorrection


class Joint:
    """Klasa bazowa wszystkich złączy - patrz opis na górze pliku."""

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 frameAngle: float = 0.0, tag: str = "") -> None:
        self.body0 = body0
        self.body1 = body1
        self.tag = tag
        """Etykieta grupy - po niej World.release(tag) potrafi zwolnić
        wybrane więzy (np. wszystkie linki procy) w trakcie symulacji."""

        self.disabled = False
        """True -> złącze pomijane przez solver. Tak działa 'przecięcie liny':
        nie usuwamy obiektu (bo chcemy go mieć w historii i statystykach),
        tylko wyłączamy."""

        # --- MONTAŻ: przeliczenie punktu i kąta na układy lokalne obu ciał
        self.localPos0 = body0.worldToLocal(anchor)
        self.localPos1 = body1.worldToLocal(anchor)
        self.localRot0 = frameAngle - body0.rot
        self.localRot1 = frameAngle - body1.rot

        # --- bufory na aktualne (globalne) ramki
        self.globalPos0 = anchor.clone()
        self.globalPos1 = anchor.clone()
        self.globalRot0 = frameAngle
        self.globalRot1 = frameAngle

        # --- diagnostyka: ile "kosztuje" utrzymanie tego więzu
        self.force = 0.0          # siła więzu [N]  = lambda/dt^2
        self.torque = 0.0         # moment więzu [Nm]
        self.elongation = 0.0     # rozjazd ponad długość spoczynkową [m]

    # ---- ramki ----------------------------------------------------------
    def updateGlobalFrames(self) -> None:
        """Gdzie SĄ TERAZ obie ramki zaczepienia.

        Wołane na początku KAŻDEGO klocka, a nie raz na podkrok - i to jest
        celowe. Klocki wykonują się po kolei, każdy zmienia stan ciał, więc
        następny musi patrzeć na stan już poprawiony. To istota metody
        Gaussa-Seidla, na której stoi cała zbieżność solvera."""
        self.globalPos0 = self.body0.localToWorld(self.localPos0)
        self.globalPos1 = self.body1.localToWorld(self.localPos1)
        self.globalRot0 = self.body0.rot + self.localRot0
        self.globalRot1 = self.body1.rot + self.localRot1

    def relativeAngle(self) -> float:
        """Kąt między ramkami, sprowadzony do (-pi, pi]."""
        return normalizeAngle(self.globalRot1 - self.globalRot0)

    # ---- METODA SZABLONOWA ----------------------------------------------
    def solve(self) -> None:
        """Stały scenariusz, zmienna treść.

        Kolejność ma znaczenie: najpierw punkty, potem kąty. Odwrotna też by
        działała, ale zbiegałaby wolniej, bo korekta kątowa przesuwa punkty
        zaczepienia - lepiej, żeby była ostatnia."""
        if self.disabled:
            return
        self.solvePosition()
        self.solveOrientation()

    def solvePosition(self) -> None:
        """Do nadpisania: więzy na POŁOŻENIE punktów zaczepienia."""

    def solveOrientation(self) -> None:
        """Do nadpisania: więzy na KĄT względny ciał."""

    def solveVelocity(self, dt: float) -> None:
        """Do nadpisania: korekty na POZIOMIE PRĘDKOŚCI (tłumienie, napędy).
        Wołane po updateVelocities, gdy prędkości są już policzone."""

    # =====================================================================
    #  KLOCKI (Building Blocks ze slajdów)
    # =====================================================================

    def attach(self, restDistance: float = 0.0, compliance: float = 0.0,
               unilateral: bool = False) -> None:
        """Attach(p1, p2, d_rest, alpha) - trzyma punkty w zadanej odległości.

            restDistance = 0   -> punkty mają się pokrywać (zawias, spaw)
            restDistance = L   -> odległość dokładnie L (pręt, linka)
            unilateral = True  -> więz jednostronny: działa tylko gdy
                                  odległość jest ZA DUŻA. Tak zachowuje się
                                  lina - można ją zwinąć, nie można rozciągnąć.
        """
        self.updateGlobalFrames()
        d = Vec2().subtractVectors(self.globalPos1, self.globalPos0)
        dist = d.length()
        if dist == 0.0:
            return                       # punkty się pokrywają - brak kierunku
        self.elongation = dist - restDistance
        if unilateral and self.elongation < 0.0:
            self.force = 0.0             # lina luźna - zero siły
            return
        corr = d.scale(self.elongation / dist)   # wektor o długości C
        self.force = applyLinearCorrection(corr, self.body0, self.globalPos0,
                                           self.body1, self.globalPos1,
                                           compliance)

    def alignAngle(self, targetAngle: float = 0.0,
                   compliance: float = 0.0) -> None:
        """AlignAxes(a1, a2, alpha) - wymusza zadany kąt względny ramek.

        W 3D potrzebny był iloczyn wektorowy dwóch osi, bo osi obrotu jest
        wiele. W 2D oś jest jedna, więc "kąt względny" to zwykła liczba
        i cały więz sprowadza się do odejmowania."""
        self.updateGlobalFrames()
        corr = normalizeAngle(self.relativeAngle() - targetAngle)
        self.torque = applyAngularCorrection(corr, self.body0, self.body1,
                                             compliance)

    def limitAngle(self, minAngle: float, maxAngle: float,
                   compliance: float = 0.0) -> None:
        """LimitAngle(...) - ogranicznik zakresu kąta.

        Wewnątrz przedziału NIE ROBI NIC (przegub swobodny), po przekroczeniu
        popycha z powrotem dokładnie do krawędzi - kątowy odpowiednik liny.
        Sztuczka: min = max = fi zamienia ogranicznik w serwo trzymające kąt.
        Tak właśnie u Müllera z jednego klocka powstają Hinge, Servo i Motor."""
        self.updateGlobalFrames()
        phi = self.relativeAngle()
        if minAngle <= phi <= maxAngle:
            return
        phiClamped = clamp(phi, minAngle, maxAngle)
        self.torque = applyAngularCorrection(normalizeAngle(phi - phiClamped),
                                             self.body0, self.body1, compliance)

    def restrictToAxis(self, minP: float, maxP: float,
                       compliance: float = 0.0) -> None:
        """RestrictToAxis(a, p1, p2, p_min, p_max, alpha) - ruch tylko wzdłuż
        osi x ramki 0, przesunięcie ograniczone do [minP, maxP].

        Działanie: różnicę punktów przenosimy do układu ramki 0, zerujemy
        składową prostopadłą (y) i przycinamy równoległą (x) do zakresu,
        po czym wracamy do świata i zlecamy korektę."""
        self.updateGlobalFrames()
        d = Vec2().subtractVectors(self.globalPos1, self.globalPos0)
        d.rotate(-self.globalRot0)             # do układu ramki 0
        if d.x > maxP:
            d.x -= maxP
        elif d.x < minP:
            d.x -= minP
        else:
            d.x = 0.0                          # w zakresie -> brak korekty
        d.rotate(self.globalRot0)              # z powrotem do świata
        self.force = applyLinearCorrection(d, self.body0, self.globalPos0,
                                           self.body1, self.globalPos1,
                                           compliance)

    # ---- tłumienie (poziom prędkości) -----------------------------------
    def dampAngular(self, dt: float, coeff: float) -> None:
        """DampAngular - zbliża prędkości kątowe obu ciał.

        To nie jest tarcie w sensie fizycznym, tylko wygaszanie drgań.
        Mnożnik min(coeff*dt, 1) gwarantuje, że nigdy nie odejmiemy więcej
        niż całą różnicę prędkości - inaczej tłumienie zaczęłoby rozkręcać
        układ w drugą stronę."""
        if coeff <= 0.0:
            return
        corr = (self.body1.omega - self.body0.omega) * min(coeff * dt, 1.0)
        applyAngularCorrection(corr, self.body0, self.body1, 0.0,
                               velocityLevel=True)

    def dampLinear(self, dt: float, coeff: float) -> None:
        """DampLinear - tłumi względny ruch punktów zaczepienia.

        velocityAt() liczy prędkość PUNKTU (v + omega x r), a nie środka masy,
        bo to punkt zaczepienia ma przestać drgać. Bez tego łańcuch ogniw
        drga w nieskończoność."""
        if coeff <= 0.0:
            return
        self.updateGlobalFrames()
        dv = Vec2().subtractVectors(self.body1.velocityAt(self.globalPos1),
                                    self.body0.velocityAt(self.globalPos0))
        dv.scale(min(coeff * dt, 1.0))
        applyLinearCorrection(dv, self.body0, self.globalPos0,
                              self.body1, self.globalPos1, 0.0,
                              velocityLevel=True)

    def __repr__(self) -> str:
        state = "OFF" if self.disabled else "ON"
        return (f"{type(self).__name__}({self.body0.name!r}<->"
                f"{self.body1.name!r}, tag={self.tag!r}, {state})")


# =============================================================================
#  TRZY ZŁĄCZA PODSTAWOWE
# =============================================================================

class RopeJoint(Joint):
    """LINKA / PRĘT.   Attach(p1, p2, d_rest = length, alpha)

        unilateral = True  -> linka: trzyma tylko przy rozciąganiu
        unilateral = False -> sztywny pręt: trzyma dokładnie zadaną długość

    Punkty zaczepienia mogą leżeć w różnych miejscach obu ciał, dlatego
    konstruktor przyjmuje anchor0 i anchor1 osobno.
    """

    def __init__(self, body0: Body, body1: Body,
                 anchor0: Vec2, anchor1: Vec2,
                 length: Optional[float] = None, compliance: float = 0.0,
                 unilateral: bool = True, damping: float = 0.2,
                 tag: str = "") -> None:
        super().__init__(body0, body1, anchor0, tag=tag)
        self.localPos1 = body1.worldToLocal(anchor1)     # drugi koniec osobno
        self.globalPos1 = anchor1.clone()
        if length is None:                  # domyślnie z geometrii sceny
            length = Vec2().subtractVectors(anchor1, anchor0).length()
        self.length = length
        self.compliance = compliance
        self.unilateral = unilateral
        self.dampingCoeff = damping

    def solvePosition(self) -> None:
        self.attach(self.length, self.compliance, self.unilateral)

    def solveVelocity(self, dt: float) -> None:
        self.dampLinear(dt, self.dampingCoeff)


class RevoluteJoint(Joint):
    """ZAWIAS (złącze ruchome).
        Attach(p1, p2, d_rest = 0, alpha = 0)
        LimitAngle(...)  - opcjonalnie

    Punkty się pokrywają, kąt względny swobodny albo ograniczony.
    minAngle = maxAngle = fi daje serwo trzymające zadany kąt.
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 minAngle: Optional[float] = None,
                 maxAngle: Optional[float] = None,
                 compliance: float = 0.0, damping: float = 0.0,
                 tag: str = "") -> None:
        super().__init__(body0, body1, anchor, tag=tag)
        self.compliance = compliance
        self.minAngle = minAngle
        self.maxAngle = maxAngle
        self.dampingCoeff = damping

    def solvePosition(self) -> None:
        self.attach(0.0, self.compliance)

    def solveOrientation(self) -> None:
        if self.minAngle is None and self.maxAngle is None:
            return                      # zawias całkiem swobodny
        lo = self.minAngle if self.minAngle is not None else -math.pi
        hi = self.maxAngle if self.maxAngle is not None else math.pi
        self.limitAngle(lo, hi)

    def solveVelocity(self, dt: float) -> None:
        self.dampAngular(dt, self.dampingCoeff)


class FixedJoint(Joint):
    """SPAW (złącze stałe).
        Attach(p1, p2, d_rest = 0, alpha = 0)
        AlignAxes(a1, a2, alpha = 0)

    Dwa ciała spięte tym złączem zachowują się jak jedna bryła.
    compliance > 0 daje spaw sprężysty (belka lekko podatna).

    restAngle jest zapamiętywany PRZY MONTAŻU, żeby nie prostować na siłę
    elementów zbudowanych pod kątem (np. nóg trójkąta).
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 compliance: float = 0.0, angularCompliance: float = 0.0,
                 tag: str = "") -> None:
        super().__init__(body0, body1, anchor, tag=tag)
        self.compliance = compliance
        self.angularCompliance = angularCompliance
        self.restAngle = self.relativeAngle()

    def solvePosition(self) -> None:
        self.attach(0.0, self.compliance)

    def solveOrientation(self) -> None:
        self.alignAngle(self.restAngle, self.angularCompliance)


# =============================================================================
#  PRZYKŁADY ROZBUDOWY - każdy to inne złożenie tych samych klocków
# =============================================================================

class SpringJoint(RopeJoint):
    """SPRĘŻYNA - linka z celową podatnością.

    Pokazuje, do czego naprawdę służy compliance: alpha [m/N] jest ODWROTNOŚCIĄ
    sztywności, więc compliance = 1/k. Sprężyna o k = 5000 N/m to
    compliance = 2e-4. Dwustronna (unilateral = False), bo sprężyna zarówno
    ciągnie, jak i pcha.

    UWAGA na typowe nieporozumienie: dodatnia compliance to CELOWA sprężystość,
    a nie lekarstwo na rozciągające się liny. Gumujące się liny to problem
    ZBIEŻNOŚCI (za mała masa ogniw / za mało podkroków), nie sztywności.
    """

    def __init__(self, body0: Body, body1: Body,
                 anchor0: Vec2, anchor1: Vec2,
                 stiffness: float = 5000.0, length: Optional[float] = None,
                 damping: float = 1.0, tag: str = "") -> None:
        super().__init__(body0, body1, anchor0, anchor1, length,
                         compliance=1.0 / stiffness, unilateral=False,
                         damping=damping, tag=tag)
        self.stiffness = stiffness


class MotorJoint(RevoluteJoint):
    """NAPĘD OBROTOWY o zadanej prędkości (slajd "Velocity Motor").

        Attach + LimitAngle(fi_motor, fi_motor)
        fi_motor <- fi_motor + dt * omega_motor

    Czyli: to jest serwo, którego kąt docelowy sam się przesuwa w czasie.
    Cały "silnik" to trzy linijki - reszta to odziedziczony zawias.
    Ustawienie compliance > 0 daje napęd o ograniczonym momencie (silnik,
    który da się zatrzymać ręką).
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 velocity: float = 1.0, compliance: float = 0.0,
                 tag: str = "") -> None:
        super().__init__(body0, body1, anchor, tag=tag)
        self.velocity = velocity           # [rad/s]
        self.targetAngle = 0.0
        self.motorCompliance = compliance

    def solveOrientation(self) -> None:
        self.targetAngle = normalizeAngle(
            self.targetAngle + self.velocity * self.body1.dt)
        self.limitAngle(self.targetAngle, self.targetAngle,
                        self.motorCompliance)


class PrismaticJoint(Joint):
    """SUWAK - ruch tylko wzdłuż jednej osi, bez obrotu.
        RestrictToAxis(a1, p1, p2, p_min, p_max, alpha)
        AlignAxes(a1, a2, alpha = 0)

    Przykład: tłok w cylindrze, prowadnica, teleskopowe ramię.
    axisAngle podaje kierunek prowadnicy w chwili montażu.
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 axisAngle: float = 0.0, minP: float = 0.0, maxP: float = 0.0,
                 compliance: float = 0.0, damping: float = 0.0,
                 tag: str = "") -> None:
        super().__init__(body0, body1, anchor, frameAngle=axisAngle, tag=tag)
        self.minP = minP
        self.maxP = maxP
        self.compliance = compliance
        self.restAngle = self.relativeAngle()
        self.dampingCoeff = damping

    def solvePosition(self) -> None:
        self.restrictToAxis(self.minP, self.maxP, self.compliance)

    def solveOrientation(self) -> None:
        self.alignAngle(self.restAngle, 0.0)

    def solveVelocity(self, dt: float) -> None:
        self.dampLinear(dt, self.dampingCoeff)
