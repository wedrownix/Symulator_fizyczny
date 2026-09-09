import math
from typing import List, Optional

# =============================================================================
# %% 1. WEKTOR 2D
# =============================================================================
from Vector2_finally import Vec2, normalizeAngle



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

