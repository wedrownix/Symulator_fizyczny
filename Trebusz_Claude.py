"""
===============================================================================
 SAMOUCZEK 25 -- ZŁĄCZA (JOINTS) MIĘDZY BRYŁAMI SZTYWNYMI W 2D, XPBD
 (na podstawie: Matthias Müller, Ten Minute Physics, tutorial 25 "Joint
  Simulation" - kod three.js + slajdy; kontynuacja samouczka 22)
===============================================================================

CO TU JEST
----------
Silnik XPBD dla brył sztywnych 2D + trzy złącza:
    RopeJoint       linka / pręt   (Attach z zadaną długością)
    RevoluteJoint   zawias         (Attach + opcjonalny LimitAngle)
    FixedJoint      spaw           (Attach + AlignAngle)
oraz prosty builder, żeby scenę składać z klocków w kilku linijkach.
Bez interfejsu, bez myszy - jeden rysunek na ekranie.

DLACZEGO TYLKO XPBD
-------------------
Różnica PBD vs XPBD to JEDEN wzór na mnożnik Lagrange'a:
    PBD :  lambda = -s * C / (w1 + w2)              s - liczba niefizyczna
    XPBD:  lambda = -C / (w1 + w2 + alpha/dt^2)     alpha = 1/sztywność [m/N]
Dla alpha = 0 oba dają dokładnie to samo (więz nieskończenie sztywny), a XPBD
dodatkowo daje wynik niezależny od dt. Nie ma więc po co trzymać dwóch
ścieżek - w całym pliku jest XPBD, a compliance = 0.0 to domyślna wartość.

KLOCKI ZE SLAJDÓW ("Building Blocks")
-------------------------------------
Wszystkie złącza są złożone z czterech elementarnych operacji:
    ApplyLinearCorrection (p1, p2, dp, alpha)   -> applyLinearCorrection()
    ApplyAngularCorrection(dfi, alpha)          -> applyAngularCorrection()
    Attach    (p1, p2, d_rest, alpha)           -> Joint.attach()
    AlignAxes / LimitAngle                      -> Joint.alignAngle() / limitAngle()
W 2D "AlignAxes" i "LimitAngle" zlewają się w jedno, bo oś obrotu jest tylko
jedna (prostopadła do ekranu) i kąt względny jest zwykłą liczbą.

MOMENT BEZWŁADNOŚCI A OŚ OBROTU
-------------------------------
I jest ZAWSZE liczone względem środka masy. Wpływ położenia osi wchodzi sam,
przez człon (r x n)^2 / I w uogólnionej masie odwrotnej - to jest twierdzenie
Steinera liczone w locie dla aktualnego punktu zaczepienia. Belka zawieszona
na końcu automatycznie "waży" I_c + m*d^2, nic nie trzeba podawać.
Dla ciał złożonych (kilka kawałków traktowanych jako jedna bryła) można podać
inertia= ręcznie: I = suma(I_i + m_i * d_i^2).
UWAGA: z tablic bierzemy zawsze wersję WZGLĘDEM ŚRODKA (pręt: mL^2/12),
nigdy względem końca (mL^2/3) - resztę dołoży solver.

Sterowanie: SPACJA pauza, R restart, ESC wyjście.
===============================================================================
"""

import math
from typing import List, Optional
import pygame

pygame.init()


# =============================================================================
# %% 1. WEKTOR 2D
# =============================================================================

class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x, self.y = x, y

    def clone(self) -> "Vec2":
        return Vec2(self.x, self.y)

    def set(self, v: "Vec2") -> "Vec2":
        self.x, self.y = v.x, v.y
        return self

    def add(self, v: "Vec2", s: float = 1.0) -> "Vec2":
        self.x += v.x * s
        self.y += v.y * s
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

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def lengthSq(self) -> float:
        return self.x * self.x + self.y * self.y

    def dot(self, v: "Vec2") -> float:
        return self.x * v.x + self.y * v.y

    def cross(self, v: "Vec2") -> float:
        """W 3D iloczyn wektorowy daje wektor; w 2D - skalar (składową z)."""
        return self.x * v.y - self.y * v.x

    def rotate(self, angle: float) -> "Vec2":
        """Zastępuje applyQuaternion(rot); obrót o -angle zastępuje invRot."""
        c, s = math.cos(angle), math.sin(angle)
        self.x, self.y = c * self.x - s * self.y, s * self.x + c * self.y
        return self

    def rotated(self, angle: float) -> "Vec2":
        return self.clone().rotate(angle)

    def isFinite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)


def normalizeAngle(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


# =============================================================================
# %% 2. ZABEZPIECZENIA NUMERYCZNE
# =============================================================================
# Po co to jest:
# W poprzedniej wersji przy bardzo mocnym naciągnięciu układu prostokąty
# "świrowały" - wyglądały jak spłaszczone i latały po ekranie bez końca.
# Przyczyna nie jest graficzna, tylko numeryczna, i ma trzy warstwy:
#
#  1. Duże naruszenie więzu C daje w jednym podkroku dużą korektę położenia.
#     Ta korekta zamienia się potem na prędkość przez v = (x - prev)/dt, więc
#     przy małym dt z korekty 0.1 m robi się prędkość rzędu setek m/s.
#  2. Korekta przyłożona z dala od środka masy daje przyrost kąta
#     invI * (r x p). Przy dużym p to może być kilka radianów W JEDNYM
#     PODKROKU. Obrót o kilka radianów w kroku łamie założenie o małych
#     kątach, na którym opiera się linearyzacja - układ dostaje energię
#     zamiast ją tracić i rozkręca się sam.
#  3. Gdy współrzędne urosną do 1e6 i więcej, cX/cY zwracają liczby poza
#     zakresem int obsługiwanym przez pygame - wtedy wielokąt rysuje się
#     ze zwiniętymi wierzchołkami i WYGLĄDA jak spłaszczony prostokąt.
#     To już tylko objaw, ale to on rzuca się w oczy.
#
# Lekarstwo: ograniczamy przyrost kąta z pojedynczej korekty i obcinamy
# prędkości. To nie jest fizyka, tylko bezpiecznik - w normalnej symulacji
# te limity nigdy się nie aktywują, a w patologicznej powstrzymują lawinę.
# Ponadto rysowanie pomija ciała o nieskończonych/absurdalnych współrzędnych.

MAX_ROT_CORRECTION = 0.5      # [rad] maksymalny obrót z jednej korekty
MAX_SPEED = 100.0             # [m/s]
MAX_OMEGA = 50.0              # [rad/s]
MAX_COORD = 1.0e4             # [m] dalej uznajemy ciało za "uciekłe"


# =============================================================================
# %% 3. BRYŁA SZTYWNA
# =============================================================================

class Body:
    """Stan: pos (x), rot (q), vel (v), omega (w).
    mass <= 0  ->  ciało nieruchome (invMass = invInertia = 0).

    inertia:
        None  -> policzone przez podklasę ze wzoru dla kształtu
        liczba -> podane ręcznie (ciała złożone, twierdzenie Steinera)
    """

    def __init__(self, pos: Vec2, angle: float = 0.0, mass: float = 0.0,
                 inertia: float = 0.0, color=(210, 210, 215)):
        self.pos = pos.clone()
        self.rot = angle
        self.vel = Vec2()
        self.omega = 0.0

        self.prevPos = pos.clone()
        self.prevRot = angle

        self.mass = mass
        self.inertia = inertia
        self.invMass = 1.0 / mass if mass > 0.0 else 0.0
        self.invInertia = 1.0 / inertia if inertia > 0.0 else 0.0

        self.dt = 1.0 / 60.0
        self.damping = 0.0
        self.color = color

    @property
    def isStatic(self) -> bool:
        return self.invMass == 0.0 and self.invInertia == 0.0

    # ---- transformacje --------------------------------------------------
    def localToWorld(self, localPos: Vec2) -> Vec2:
        """a' = x + q*a  -- punkt przyklejony do ciała, wyrażony w świecie."""
        return localPos.rotated(self.rot).add(self.pos)

    def worldToLocal(self, worldPos: Vec2) -> Vec2:
        """a = q^-1*(a' - x)  -- robimy to raz, przy tworzeniu złącza."""
        return Vec2().subtractVectors(worldPos, self.pos).rotate(-self.rot)

    def velocityAt(self, worldPos: Vec2) -> Vec2:
        """v_a = v + omega x r."""
        r = Vec2().subtractVectors(worldPos, self.pos)
        return Vec2(self.vel.x - self.omega * r.y,
                    self.vel.y + self.omega * r.x)

    # ---- krok symulacji -------------------------------------------------
    def integrate(self, dt: float, gravity: Vec2) -> None:
        """v <- v + dt*g ;  x <- x + dt*v ;  q <- q + dt*omega
        Ciało leci swobodnie, więzy chwilowo zignorowane."""
        self.dt = dt
        if self.isStatic:
            return
        self.prevPos.set(self.pos)
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)
        self.prevRot = self.rot
        self.rot += self.omega * dt

    def updateVelocities(self) -> None:
        """v <- (x - x_prev)/dt ;  omega <- (q - q_prev)/dt
        Prędkość czytana z faktycznego przesunięcia po korektach."""
        if self.isStatic:
            return
        self.vel.subtractVectors(self.pos, self.prevPos).scale(1.0 / self.dt)
        self.omega = normalizeAngle(self.rot - self.prevRot) / self.dt

        if self.damping > 0.0:
            f = max(1.0 - self.damping * self.dt, 0.0)
            self.vel.scale(f)
            self.omega *= f

        # bezpieczniki (patrz sekcja 2)
        v = self.vel.length()
        if v > MAX_SPEED:
            self.vel.scale(MAX_SPEED / v)
        if abs(self.omega) > MAX_OMEGA:
            self.omega = math.copysign(MAX_OMEGA, self.omega)

    # ---- uogólniona masa odwrotna ---------------------------------------
    def getInverseMass(self, normal: Vec2, worldPos: Optional[Vec2] = None) -> float:
        """w = 1/m + (r x n)^2 / I        (worldPos podane)
           w = 1/I                        (worldPos = None, więz kątowy)

        "O ile ustąpi TEN punkt ciała pod jednostkowym impulsem w kierunku n."
        Człon (r x n)^2/I to Steiner liczony w locie - dlatego I podajemy
        tylko względem środka masy i nigdy względem osi złącza."""
        if self.isStatic:
            return 0.0
        if worldPos is None:
            return self.invInertia
        r = Vec2().subtractVectors(worldPos, self.pos)
        rn = r.cross(normal)
        return self.invMass + rn * rn * self.invInertia

    # ---- przyłożenie korekty --------------------------------------------
    def applyImpulse(self, p: Vec2, worldPos: Vec2, velocityLevel: bool) -> None:
        """x <- x + p/m  oraz  q <- q + I^-1 (r x p).
        Druga linijka to jedyna różnica między bryłą a cząstką."""
        if self.isStatic:
            return
        r = Vec2().subtractVectors(worldPos, self.pos)
        dRot = self.invInertia * r.cross(p)
        # bezpiecznik: nie pozwalamy na obrót o więcej niż MAX_ROT_CORRECTION
        # w jednej korekcie (linearyzacja obowiązuje tylko dla małych kątów)
        if abs(dRot) > MAX_ROT_CORRECTION:
            dRot = math.copysign(MAX_ROT_CORRECTION, dRot)
        if velocityLevel:
            self.vel.add(p, self.invMass)
            self.omega += dRot
        else:
            self.pos.add(p, self.invMass)
            self.rot += dRot

    def applyTwist(self, dl: float, velocityLevel: bool) -> None:
        """Korekta czysto kątowa (bez ruchu środka masy)."""
        if self.isStatic:
            return
        d = self.invInertia * dl
        if not velocityLevel and abs(d) > MAX_ROT_CORRECTION:
            d = math.copysign(MAX_ROT_CORRECTION, d)
        if velocityLevel:
            self.omega += d
        else:
            self.rot += d

    def kineticEnergy(self) -> float:
        return 0.5 * self.mass * self.vel.lengthSq() + \
               0.5 * self.inertia * self.omega * self.omega


# --- dwa wzory ze slajdów "Linear/Angular Correction" ------------------------
# Przez te dwie funkcje przechodzą WSZYSTKIE więzy w całym silniku.

def applyLinearCorrection(corr: Vec2, body0: Body, pos0: Vec2,
                          body1: Body, pos1: Vec2,
                          compliance: float = 0.0,
                          velocityLevel: bool = False) -> float:
    """
        C      = |dp|
        n      = dp / |dp|
        w_i    = 1/m_i + ((p_i - x_i) x n)^2 / I_i
        lambda = -C / (w1 + w2 + alpha/dt^2)
        x_i   <- x_i +- lambda n / m_i
        q_i   <- q_i +- lambda I^-1 ((p_i - x_i) x n)

    Zwraca lambda/dt^2, czyli SIŁĘ więzu w niutonach.
    Konwencja: corr = ile ma zmaleć (wielkość1 - wielkość0); ciało 0 dostaje
    korektę "+", ciało 1 "-".
    """
    C = corr.length()
    if C == 0.0:
        return 0.0
    n = corr.clone().scale(1.0 / C)

    w = body0.getInverseMass(n, pos0) + body1.getInverseMass(n, pos1)
    if w == 0.0:
        return 0.0

    if velocityLevel:
        dl = C / w                                   # bez alpha (poziom prędkości)
    else:
        alpha = compliance / (body0.dt * body0.dt)   # XPBD
        dl = C / (w + alpha)

    p = n.scale(dl)
    body0.applyImpulse(p, pos0, velocityLevel)
    body1.applyImpulse(p.clone().scale(-1.0), pos1, velocityLevel)
    return dl / (body0.dt * body0.dt)


def applyAngularCorrection(corr: float, body0: Body, body1: Body,
                           compliance: float = 0.0,
                           velocityLevel: bool = False) -> float:
    """Wersja kątowa: w_i = 1/I_i, reszta identyczna.
    Zwraca lambda/dt^2, czyli MOMENT więzu w Nm."""
    if corr == 0.0:
        return 0.0
    w = body0.getInverseMass(Vec2(), None) + body1.getInverseMass(Vec2(), None)
    if w == 0.0:
        return 0.0

    if velocityLevel:
        dl = corr / w
    else:
        alpha = compliance / (body0.dt * body0.dt)
        dl = corr / (w + alpha)

    body0.applyTwist(dl, velocityLevel)
    body1.applyTwist(-dl, velocityLevel)
    return dl / (body0.dt * body0.dt)


# =============================================================================
# %% 4. KLOCKI: PROSTOKĄT I MASA PUNKTOWA
# =============================================================================

class Beam(Body):
    """Sztywny prostokąt - podstawowy materiał budowlany.
    I = m(w^2 + h^2)/12 względem środka masy.
    density = 0 -> masa 0 -> element wmurowany, nieruchomy."""

    def __init__(self, pos: Vec2, width: float, height: float,
                 density: float = 1.0, angle: float = 0.0,
                 inertia: Optional[float] = None, color=(226, 196, 118)):
        m = density * width * height
        I = m * (width * width + height * height) / 12.0 if inertia is None else inertia
        super().__init__(pos, angle, m, I, color)
        self.width, self.height = width, height

    def localAt(self, t: float) -> Vec2:
        """t in [-1, 1]: -1 lewy koniec, 0 środek, +1 prawy koniec (lokalnie)."""
        return Vec2(t * 0.5 * self.width, 0.0)

    def at(self, t: float) -> Vec2:
        """Ten sam punkt we współrzędnych świata - tym budujemy sceny."""
        return self.localToWorld(self.localAt(t))

    def end(self, sign: float = 1.0) -> Vec2:
        return self.at(sign)

    def corners(self) -> List[Vec2]:
        """
        Zwraca 4 wierzchołki prostokąta w układzie ŚWIATA, gotowe do rysowania.

        Krok po kroku:
          ex, ey = połowa szerokości i połowa wysokości. W układzie własnym
                   ciała środek masy leży w (0,0), więc wierzchołki to
                   (+-ex, +-ey) - stąd "e" jak extent (połowa rozpiętości).

          (sx, sy) przebiega cztery pary znaków:
                   (-1,-1) lewy dolny, (1,-1) prawy dolny,
                   (1, 1) prawy górny, (-1, 1) lewy górny.
                   Kolejność jest celowo "dookoła" (przeciwnie do ruchu
                   wskazówek), a nie np. po przekątnej - inaczej
                   pygame.draw.polygon narysowałby kokardkę zamiast
                   prostokąta.

          Vec2(sx*ex, sy*ey) to wierzchołek w układzie LOKALNYM: liczba stała,
                   zawsze taka sama, niezależna od tego gdzie ciało jest i jak
                   jest obrócone. Geometria ciała nie zmienia się nigdy - to
                   właśnie znaczy "bryła sztywna".

          localToWorld(...) obraca ten punkt o aktualny kąt rot i przesuwa
                   o aktualne pos, czyli stosuje wzór a' = x + q*a. Dopiero
                   tutaj wchodzi aktualny stan ciała.

        Efekt: cała informacja o ruchu siedzi w (pos, rot), a kształt jest
        stały. Dlatego prostokąt NIE MOŻE się w tym modelu zdeformować - jeśli
        na ekranie wygląda na spłaszczony, to znaczy że pos/rot są chore
        (patrz sekcja 2), a nie że geometria się zmieniła.
        """
        ex, ey = 0.5 * self.width, 0.5 * self.height
        return [self.localToWorld(Vec2(sx * ex, sy * ey))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


class PointMass(Body):
    """Punkt materialny: I = 0 -> invInertia = 0, obrót go nie dotyczy.
    Wzór na uogólnioną masę odwrotną wraca wtedy do w = 1/m."""

    def __init__(self, pos: Vec2, mass: float, radius: float = 0.05,
                 color=(90, 200, 255)):
        super().__init__(pos, 0.0, mass, 0.0, color)
        self.invInertia = 0.0
        self.radius = radius


# =============================================================================
# %% 5. ZŁĄCZA
# =============================================================================

class Joint:
    """
    Klasa bazowa. Wzorzec Metoda Szablonowa:
        solve() = solvePosition() + solveOrientation()
    a podklasy składają się z gotowych klocków ze slajdów:
        attach()      = Attach(p1, p2, d_rest, alpha)
        alignAngle()  = AlignAxes(a1, a2, alpha)      (w 2D: wyrównanie kątów)
        limitAngle()  = LimitAngle(n, a1, a2, min, max, alpha)

    RAMKI ZACZEPIENIA (slajd "Attachment Frames"):
    punkt i kąt złącza podajemy RAZ, w układzie świata, przy tworzeniu.
    Konstruktor zapamiętuje je lokalnie w obu ciałach (localPos/localRot),
    więc potem jeżdżą razem z ciałami za darmo. updateGlobalFrames()
    odtwarza aktualne położenie tych ramek w świecie.
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 frameAngle: float = 0.0):
        self.body0 = body0
        self.body1 = body1
        self.disabled = False

        self.localPos0 = body0.worldToLocal(anchor)
        self.localPos1 = body1.worldToLocal(anchor)
        self.localRot0 = frameAngle - body0.rot
        self.localRot1 = frameAngle - body1.rot

        self.globalPos0 = anchor.clone()
        self.globalPos1 = anchor.clone()
        self.globalRot0 = frameAngle
        self.globalRot1 = frameAngle

        self.force = 0.0          # ostatnia siła więzu [N]
        self.torque = 0.0         # ostatni moment więzu [Nm]
        self.elongation = 0.0     # ostatnie wydłużenie [m]

    def updateGlobalFrames(self) -> None:
        self.globalPos0 = self.body0.localToWorld(self.localPos0)
        self.globalPos1 = self.body1.localToWorld(self.localPos1)
        self.globalRot0 = self.body0.rot + self.localRot0
        self.globalRot1 = self.body1.rot + self.localRot1

    def relativeAngle(self) -> float:
        return normalizeAngle(self.globalRot1 - self.globalRot0)

    # ---- szablon --------------------------------------------------------
    def solve(self) -> None:
        if self.disabled:
            return
        self.solvePosition()
        self.solveOrientation()

    def solvePosition(self) -> None:
        pass

    def solveOrientation(self) -> None:
        pass

    def solveVelocity(self, dt: float) -> None:
        pass

    # ---- klocki ---------------------------------------------------------
    def attach(self, restDistance: float = 0.0, compliance: float = 0.0,
               unilateral: bool = False) -> None:
        """Attach(p1, p2, d_rest, alpha): trzyma punkty zaczepienia
        w odległości restDistance. restDistance = 0 -> punkty się pokrywają.
        unilateral = True -> linka (działa tylko na rozciąganie)."""
        self.updateGlobalFrames()
        d = Vec2().subtractVectors(self.globalPos1, self.globalPos0)
        dist = d.length()
        if dist == 0.0:
            return
        self.elongation = dist - restDistance
        if unilateral and self.elongation < 0.0:
            self.force = 0.0
            return
        corr = d.scale(self.elongation / dist)
        self.force = applyLinearCorrection(corr, self.body0, self.globalPos0,
                                           self.body1, self.globalPos1,
                                           compliance)

    def alignAngle(self, targetAngle: float = 0.0, compliance: float = 0.0) -> None:
        """AlignAxes: wymusza zadany kąt względny ramek."""
        self.updateGlobalFrames()
        corr = normalizeAngle(self.relativeAngle() - targetAngle)
        self.torque = applyAngularCorrection(corr, self.body0, self.body1,
                                             compliance)

    def limitAngle(self, minAngle: float, maxAngle: float,
                   compliance: float = 0.0) -> None:
        """LimitAngle: nic nie robi wewnątrz zakresu, na krawędzi popycha
        z powrotem. Ustawienie min = max daje serwo (kąt docelowy)."""
        self.updateGlobalFrames()
        phi = self.relativeAngle()
        if minAngle <= phi <= maxAngle:
            return
        phiClamped = max(minAngle, min(phi, maxAngle))
        self.torque = applyAngularCorrection(normalizeAngle(phi - phiClamped),
                                             self.body0, self.body1, compliance)

    def dampAngular(self, dt: float, coeff: float) -> None:
        """DampAngular ze slajdu: zbliża prędkości kątowe obu ciał.
        Działa na POZIOMIE PRĘDKOŚCI, czyli po updateVelocities."""
        if coeff <= 0.0:
            return
        corr = (self.body1.omega - self.body0.omega) * min(coeff * dt, 1.0)
        applyAngularCorrection(corr, self.body0, self.body1, 0.0, velocityLevel=True)

    def dampLinear(self, dt: float, coeff: float) -> None:
        """DampLinear ze slajdu: tłumi względny ruch punktów zaczepienia."""
        if coeff <= 0.0:
            return
        self.updateGlobalFrames()
        dv = Vec2().subtractVectors(self.body1.velocityAt(self.globalPos1),
                                    self.body0.velocityAt(self.globalPos0))
        dv.scale(min(coeff * dt, 1.0))
        applyLinearCorrection(dv, self.body0, self.globalPos0,
                              self.body1, self.globalPos1, 0.0, velocityLevel=True)


class RopeJoint(Joint):
    """LINKA / PRĘT.  Attach(p1, p2, d_rest = length, alpha).
    unilateral = True  -> linka: trzyma tylko przy rozciąganiu (można zwisać)
    unilateral = False -> sztywny pręt: trzyma dokładnie zadaną długość

    Dwa punkty zaczepienia mogą leżeć w różnych miejscach obu ciał, dlatego
    konstruktor przyjmuje anchor0 i anchor1 osobno."""

    def __init__(self, body0: Body, body1: Body, anchor0: Vec2, anchor1: Vec2,
                 length: Optional[float] = None, compliance: float = 0.0,
                 unilateral: bool = True, damping: float = 0.2):
        super().__init__(body0, body1, anchor0)
        self.localPos1 = body1.worldToLocal(anchor1)   # drugi koniec osobno
        self.globalPos1 = anchor1.clone()
        if length is None:                             # domyślnie z geometrii sceny
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
        LimitAngle(...)   - opcjonalnie
    Punkty się pokrywają, kąt względny swobodny albo ograniczony.
    minAngle = maxAngle = fi daje serwo trzymające zadany kąt."""

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 minAngle: Optional[float] = None,
                 maxAngle: Optional[float] = None,
                 compliance: float = 0.0, damping: float = 0.0):
        super().__init__(body0, body1, anchor)
        self.compliance = compliance
        self.minAngle = minAngle
        self.maxAngle = maxAngle
        self.dampingCoeff = damping

    def solvePosition(self) -> None:
        self.attach(0.0, self.compliance)

    def solveOrientation(self) -> None:
        if self.minAngle is None and self.maxAngle is None:
            return
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
    compliance > 0 daje spaw sprężysty (belka lekko podatna)."""

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 compliance: float = 0.0, angularCompliance: float = 0.0):
        super().__init__(body0, body1, anchor)
        self.compliance = compliance
        self.angularCompliance = angularCompliance
        self.restAngle = self.relativeAngle()      # kąt zamrożony przy montażu

    def solvePosition(self) -> None:
        self.attach(0.0, self.compliance)

    def solveOrientation(self) -> None:
        self.alignAngle(self.restAngle, self.angularCompliance)


# =============================================================================
# %% 6. ŚWIAT + BUDOWANIE Z KLOCKÓW
# =============================================================================

class World:
    """
    Pętla ze slajdu "XPBD Algorithm for Rigid Bodies" + "Velocity Step":

        for n sub-steps:
            for all bodies:      integrate v, x, omega, q
            for all joints:      solve(C)
            for all bodies:      update v, omega
            for all joints:      apply velocity corrections (tłumienie)

    Sub-stepping (slajd "Sub-Stepping"): n MAŁYCH pełnych kroków zbiega
    znacznie lepiej niż n iteracji solvera w jednym dużym kroku, przy tym
    samym koszcie. Dlatego numSubSteps jest duże, a numIterations = 1.

    Metody addBeam / addPointMass / connectFixed / connectRevolute /
    connectRope to warstwa "klocków lego" - scenę składa się nimi
    w kilku linijkach, bez dotykania solvera.
    """

    def __init__(self, gravity: Vec2 = Vec2(0.0, -9.81),
                 dt: float = 1.0 / 60.0, numSubSteps: int = 40):
        self.gravity = gravity.clone()
        self.dt = dt
        self.numSubSteps = numSubSteps
        self.bodies: List[Body] = []
        self.joints: List[Joint] = []

    def clear(self) -> None:
        self.bodies.clear()
        self.joints.clear()

    # ---- klocki ---------------------------------------------------------
    def addBeam(self, x: float, y: float, width: float, height: float,
                density: float = 1.0, angle: float = 0.0, **kw) -> Beam:
        """Prostokąt. density = 0 -> element nieruchomy (wmurowany)."""
        return self._add(Beam(Vec2(x, y), width, height, density, angle, **kw))

    def addBeamBetween(self, a: Vec2, b: Vec2, thickness: float,
                       density: float = 1.0, **kw) -> Beam:
        """Wygodniejsze przy budowaniu kratownic: belka od punktu a do b."""
        d = Vec2().subtractVectors(b, a)
        mid = Vec2().addVectors(a, b).scale(0.5)
        return self._add(Beam(mid, d.length(), thickness, density,
                              math.atan2(d.y, d.x), **kw))

    def addPointMass(self, x: float, y: float, mass: float,
                     radius: float = 0.05, **kw) -> PointMass:
        return self._add(PointMass(Vec2(x, y), mass, radius, **kw))

    def connectFixed(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> FixedJoint:
        return self._add(FixedJoint(b0, b1, anchor, **kw))

    def connectRevolute(self, b0: Body, b1: Body, anchor: Vec2, **kw) -> RevoluteJoint:
        return self._add(RevoluteJoint(b0, b1, anchor, **kw))

    def connectRope(self, b0: Body, b1: Body, anchor0: Vec2, anchor1: Vec2,
                    **kw) -> RopeJoint:
        return self._add(RopeJoint(b0, b1, anchor0, anchor1, **kw))

    def connectRopeChain(self, b0: Body, anchor0: Vec2, b1: Body, anchor1: Vec2,
                         numNodes: int = 4, nodeMass: float = 0.1,
                         length: Optional[float] = None) -> List[PointMass]:
        """Lina z ogniw: b0 --o--o--o--o-- b1. Zamiast jednego więzu robimy
        łańcuch mas punktowych, dzięki czemu lina naprawdę zwisa i faluje."""
        if length is None:
            length = Vec2().subtractVectors(anchor1, anchor0).length()
        seg = length / (numNodes + 1)
        direction = Vec2().subtractVectors(anchor1, anchor0)
        dl = direction.length()
        direction.scale(1.0 / dl if dl > 0.0 else 0.0)

        nodes: List[PointMass] = []
        prevBody, prevPoint = b0, anchor0
        for i in range(numNodes):
            p = anchor0.clone().add(direction, seg * (i + 1))
            node = self.addPointMass(p.x, p.y, nodeMass, 0.03,
                                     color=(225, 225, 225))
            self.connectRope(prevBody, node, prevPoint, p, length=seg)
            nodes.append(node)
            prevBody, prevPoint = node, p
        self.connectRope(prevBody, b1, prevPoint, anchor1, length=seg)
        return nodes

    def _add(self, obj):
        (self.joints if isinstance(obj, Joint) else self.bodies).append(obj)
        return obj

    # ---- symulacja ------------------------------------------------------
    def simulate(self) -> None:
        sdt = self.dt / self.numSubSteps
        for _ in range(self.numSubSteps):
            for b in self.bodies:
                b.integrate(sdt, self.gravity)
            for j in self.joints:
                j.solve()
            for b in self.bodies:
                b.updateVelocities()
            for j in self.joints:
                if not j.disabled:
                    j.solveVelocity(sdt)

    def totalKineticEnergy(self) -> float:
        return sum(b.kineticEnergy() for b in self.bodies)


# =============================================================================
# %% 7. OKNO I KAMERA
# =============================================================================

screen_width, screen_height = 3200, 2000
win = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Samouczek 25 - złącza XPBD 2D")
clock = pygame.time.Clock()

simMinWidth = 6.0                       # ile metrów mieści się w oknie
cScale = min(screen_width, screen_height) / simMinWidth


def cX(x: float) -> int:
    return int(screen_width * 0.5 + x * cScale)


def cY(y: float) -> int:
    return int(screen_height * 0.88 - y * cScale)


# =============================================================================
# %% 8. SCENA - PRZYKŁAD BUDOWY Z KLOCKÓW
# =============================================================================

world = World(gravity=Vec2(0.0, -9.81), dt=1.0 / 60.0, numSubSteps=40)


def setup_scene() -> None:
    """Żuraw: nieruchoma podstawa -> maszt (spaw) -> wysięgnik na zawiasie
    -> odciąg z linki -> ładunek na linie z ogniw -> wahadło na zawiasie.
    Trzy typy złączy i oba typy ciał, w kilkunastu linijkach."""
    world.clear()

    # podstawa: density = 0 -> masa nieskończona, element nieruchomy
    base = world.addBeam(0.0, 0.05, 2.0, 0.10, density=0.0, color=(120, 122, 132))

    # maszt przyspawany do podstawy (ZŁĄCZE STAŁE)
    mast = world.addBeamBetween(Vec2(0.0, 0.10), Vec2(0.0, 2.20), 0.12,
                                density=25.0, color=(176, 138, 84))
    world.connectFixed(base, mast, Vec2(0.0, 0.10))

    # zastrzał: druga belka też przyspawana - rama sztywna
    brace = world.addBeamBetween(Vec2(-0.8, 0.10), Vec2(0.0, 1.60), 0.09,
                                 density=25.0, color=(176, 138, 84))
    world.connectFixed(base, brace, Vec2(-0.8, 0.10))
    world.connectFixed(mast, brace, Vec2(0.0, 1.60))

    # wysięgnik na ZAWIASIE w szczycie masztu, z ograniczeniem kąta
    boom = world.addBeam(0, 2.20, 1.8, 0.10, density=18.0)
    world.connectRevolute(mast, boom, Vec2(0.0, 2.20),
                          minAngle=-2, maxAngle=2, damping=1.0)

    # ładunek na LINIE Z OGNIW ina faluje
    hook = world.addPointMass(1, 0.1, 1.0, 0.1, color=(205, 70, 70))
    world.connectRopeChain(boom, boom.end(1.0), hook, hook.pos.clone(),
                           numNodes=15, nodeMass=0.001)

    # ładunek na LINIE Z OGNIW
    hook = world.addPointMass(-1, 1.9, 100.0, 0.4, color=(205, 70, 70))
    world.connectRopeChain(boom, boom.end(-1.0), hook, hook.pos.clone(),
                           numNodes=5, nodeMass=0.001)




# =============================================================================
# %% 9. RYSOWANIE
# =============================================================================

SHOW_FORCES = False        # True -> podpisy z siłą i wydłużeniem przy złączach
fontSmall = pygame.font.SysFont("consolas", 22)


def draw_forces() -> None:
    """
    Podpisy przy złączach, jak w Chain Demo Müllera. Domyślnie wyłączone.

    Co robi ten blok, linijka po linijce:

      for j in world.joints          - przechodzimy po wszystkich złączach;
                                       każde zna swoje dwa punkty zaczepienia
                                       w świecie (globalPos0, globalPos1),
                                       odświeżone przy ostatnim solve().

      mx = cX(0.5*(x0 + x1)) + 10    - 0.5*(x0+x1) to ŚRODEK odcinka między
      my = cY(0.5*(y0 + y1)) - 8       punktami zaczepienia, czyli miejsce,
                                       gdzie wizualnie leży złącze. cX/cY
                                       zamieniają metry na piksele. +10 i -8
                                       to przesunięcie w pikselach, żeby tekst
                                       nie leżał NA złączu, tylko obok niego
                                       (w prawo i lekko w górę).

      j.force                        - siła więzu w niutonach, czyli lambda/dt^2
                                       policzone w applyLinearCorrection.
                                       Format {:5.0f} rezerwuje 5 znaków
                                       i zaokrągla do całości, żeby liczby
                                       nie skakały na boki co klatkę.

      j.elongation * 1000            - wydłużenie w metrach zamieniane na
                                       milimetry (stąd *1000), bo dla sztywnego
                                       więzu to są ułamki milimetra. Format
                                       {:+.1f} wymusza znak + lub -, więc od
                                       razu widać, czy więz jest rozciągnięty
                                       czy ściśnięty.

      fontSmall.render(...)          - zamienia napis na małą bitmapę (True =
                                       antyaliasing, potem kolor RGB).
      win.blit(bitmapa, (mx, my))    - wkleja tę bitmapę na ekran w policzonym
                                       miejscu. blit nie rysuje kształtów,
                                       tylko kopiuje gotowe piksele.

    Wniosek diagnostyczny: jeśli siły są rzędu ciężaru tego, co wisi poniżej,
    a wydłużenia to ułamki milimetra - solver zbiega poprawnie. Jeśli
    wydłużenia rosną, to znaczy że trzeba więcej podkroków.
    """
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
            pygame.draw.line(win, (238, 238, 238), p0,
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
        # i rysuje "spłaszczone" wielokąty (patrz sekcja 2)
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

    pygame.display.update()


# =============================================================================
# %% 10. PĘTLA GŁÓWNA
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
            elif event.key == pygame.K_r:
                setup_scene()

    if not paused:
        world.simulate()
    draw()
    clock.tick(60)

pygame.quit()
