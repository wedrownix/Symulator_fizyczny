"""
pbd2d/bodies.py -- bryła sztywna i konkretne kształty (materiał budowlany).

HIERARCHIA
    Body            stan + kinematyka + reakcja na korekty (bez kształtu)
      Beam          prostokąt - podstawowy klocek
      Disk          koło - przykład rozbudowy (inny wzór na I)
      PointMass     punkt materialny (I = 0)
      CompositeBeam przykład ciała złożonego z ręcznym I (Steiner)

MOMENT BEZWŁADNOŚCI A OŚ OBROTU (częste nieporozumienie)
    I jest ZAWSZE liczone względem środka masy i NIGDY względem osi złącza.
    Wpływ położenia osi wchodzi sam, przez człon (r x n)^2/I w uogólnionej
    masie odwrotnej - to twierdzenie Steinera liczone w locie dla aktualnego
    punktu zaczepienia. Belka zawieszona na końcu automatycznie "waży"
    I_c + m*d^2, bez podawania czegokolwiek.
    Z tablic bierzemy więc wersję WZGLĘDEM ŚRODKA (pręt: mL^2/12), nigdy
    względem końca (mL^2/3).
    Wyjątek: ciało ZŁOŻONE z kilku kawałków traktowane jako jedna bryła -
    tam I trzeba policzyć ręcznie, patrz CompositeBeam.
"""

from __future__ import annotations
import math
from typing import List, Optional
from .vector2 import Vec2, normalizeAngle
from .config import SolverConfig


class Body:
    """Bryła sztywna w 2D.

    STAN (slajd "Orientational Quantities"):
        pos    x      położenie środka masy      [m]
        vel    v      prędkość środka masy       [m/s]
        rot    q      orientacja (w 2D: kąt)     [rad]
        omega  w      prędkość kątowa            [rad/s]

    PARAMETRY:
        invMass    = 1/m   opór na siłę
        invInertia = 1/I   opór na moment siły

    mass <= 0 -> ciało nieruchome (invMass = invInertia = 0). To ta sama
    umowa co "masa 0 = nieskończona masa" w klasycznym wahadle PBD.
    """

    def __init__(self, pos: Vec2, angle: float = 0.0, mass: float = 0.0,
                 inertia: float = 0.0, color=(210, 210, 215),
                 name: str = "") -> None:
        self.pos = pos.clone()
        self.rot = angle
        self.vel = Vec2()
        self.omega = 0.0

        # PBD potrzebuje pamięci "gdzie byłem przed krokiem" - z tego
        # odtwarzana jest prędkość na końcu kroku
        self.prevPos = pos.clone()
        self.prevRot = angle

        self.mass = mass
        self.inertia = inertia
        self.invMass = 1.0 / mass if mass > 0.0 else 0.0
        self.invInertia = 1.0 / inertia if inertia > 0.0 else 0.0

        self.dt = 1.0 / 60.0
        self.damping = 0.0                 # sztuczne tłumienie prędkości
        self.color = color
        self.name = name
        self.config = SolverConfig()       # nadpisywane przez World.add()

    @property
    def isStatic(self) -> bool:
        return self.invMass == 0.0 and self.invInertia == 0.0

    # ---- transformacje (slajd "Attachment Frames") ----------------------
    def localToWorld(self, localPos: Vec2) -> Vec2:
        """a' = x + q*a. Punkt przyklejony do ciała -> gdzie jest w świecie."""
        return localPos.rotated(self.rot).add(self.pos)

    def worldToLocal(self, worldPos: Vec2) -> Vec2:
        """a = q^-1*(a' - x). Robione raz, przy montażu złącza."""
        return Vec2().subtractVectors(worldPos, self.pos).rotate(-self.rot)

    def velocityAt(self, worldPos: Vec2) -> Vec2:
        """Prędkość PUNKTU ciała: v_a = v + omega x r.
        W 2D: omega x r = omega * (-r.y, r.x)."""
        r = Vec2().subtractVectors(worldPos, self.pos)
        return Vec2(self.vel.x - self.omega * r.y,
                    self.vel.y + self.omega * r.x)

    # ---- krok symulacji -------------------------------------------------
    def integrate(self, dt: float, gravity: Vec2) -> None:
        """v <- v + dt*g ;  x <- x + dt*v ;  q <- q + dt*omega

        Ciało leci swobodnie, więzy są chwilowo ignorowane - w PBD to jest
        zamierzone. Zaraz przyjdzie solver i wciągnie je z powrotem, a różnica
        położeń zamieni się na nową prędkość."""
        self.dt = dt
        if self.isStatic:
            return
        self.prevPos.set(self.pos)
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)
        self.prevRot = self.rot
        self.rot += self.omega * dt
        # w 3D trzeba tu jeszcze normalizować kwaternion i uwzględniać człon
        # żyroskopowy omega x I*omega; w 2D oba znikają

    def updateVelocities(self) -> None:
        """v <- (x - x_prev)/dt ;  omega <- (q - q_prev)/dt

        Serce PBD: prędkość nie jest całkowana z sił, tylko odczytana z tego,
        jak ciało FAKTYCZNIE się przesunęło po korektach więzów. Dlatego więz,
        który zatrzymał ciało, automatycznie zabiera mu pęd."""
        if self.isStatic:
            return
        self.vel.subtractVectors(self.pos, self.prevPos).scale(1.0 / self.dt)
        self.omega = normalizeAngle(self.rot - self.prevRot) / self.dt

        if self.damping > 0.0:
            f = max(1.0 - self.damping * self.dt, 0.0)
            self.vel.scale(f)
            self.omega *= f

        # bezpieczniki numeryczne (patrz config.SolverConfig)
        cfg = self.config
        v = self.vel.length()
        if v > cfg.maxSpeed:
            self.vel.scale(cfg.maxSpeed / v)
        if abs(self.omega) > cfg.maxOmega:
            self.omega = math.copysign(cfg.maxOmega, self.omega)

    # ---- uogólniona masa odwrotna ---------------------------------------
    def getInverseMass(self, normal: Optional[Vec2],
                       worldPos: Optional[Vec2] = None) -> float:
        """w = 1/m + (r x n)^2 / I     (worldPos podane -> więz punktowy)
           w = 1/I                     (worldPos = None -> więz kątowy)

        Czytaj to jako: "o ile przesunie się TEN punkt ciała, jeśli pchnę go
        jednostkowym impulsem w kierunku n". Pchnięcie w środek masy (r = 0)
        daje samo 1/m; pchnięcie prostopadle w koniec belki daje duże (r x n),
        więc impuls idzie głównie w obrót i koniec belki łatwo ustępuje."""
        if self.isStatic:
            return 0.0
        if worldPos is None:
            return self.invInertia
        r = Vec2().subtractVectors(worldPos, self.pos)
        rn = r.cross(normal)
        return self.invMass + rn * rn * self.invInertia

    # ---- reakcja na korektę ---------------------------------------------
    def applyImpulse(self, p: Vec2, worldPos: Vec2,
                     velocityLevel: bool = False) -> None:
        """x <- x + p/m   oraz   q <- q + I^-1 (r x p)

        Druga linijka to JEDYNA różnica między bryłą sztywną a cząstką:
        korekta przyłożona z dala od środka masy dodatkowo obraca ciało."""
        if self.isStatic:
            return
        r = Vec2().subtractVectors(worldPos, self.pos)
        dRot = self.invInertia * r.cross(p)
        limit = self.config.maxRotCorrection
        if abs(dRot) > limit:                      # bezpiecznik
            dRot = math.copysign(limit, dRot)
        if velocityLevel:
            self.vel.add(p, self.invMass)
            self.omega += dRot
        else:
            self.pos.add(p, self.invMass)
            self.rot += dRot

    def applyTwist(self, dl: float, velocityLevel: bool = False) -> None:
        """Korekta czysto kątowa - bez ruchu środka masy."""
        if self.isStatic:
            return
        d = self.invInertia * dl
        limit = self.config.maxRotCorrection
        if not velocityLevel and abs(d) > limit:
            d = math.copysign(limit, d)
        if velocityLevel:
            self.omega += d
        else:
            self.rot += d

    # ---- energia (używane przez Analyzer) -------------------------------
    def kineticEnergy(self) -> float:
        """Ek = 1/2 m v^2 + 1/2 I omega^2 (postępowa + obrotowa)."""
        return (0.5 * self.mass * self.vel.lengthSq() +
                0.5 * self.inertia * self.omega * self.omega)

    def potentialEnergy(self, g: float, refY: float = 0.0) -> float:
        """Ep = m g (y - refY)."""
        return self.mass * g * (self.pos.y - refY)

    def isSane(self) -> bool:
        """Czy ciało nadaje się do narysowania (nie uciekło w nieskończoność)."""
        return (self.pos.isFinite() and
                abs(self.pos.x) < self.config.maxCoord and
                abs(self.pos.y) < self.config.maxCoord)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r}, m={self.mass:.3g})"


# =============================================================================
#  KSZTAŁTY
# =============================================================================

class Beam(Body):
    """Prostokąt - podstawowy klocek konstrukcyjny.

    Oś lokalna x biegnie WZDŁUŻ belki, środek masy w środku geometrycznym.
    I = m(w^2 + h^2)/12  (względem środka masy).
    density = 0 -> masa 0 -> element wmurowany, nieruchomy.
    """

    def __init__(self, pos: Vec2, width: float, height: float,
                 density: float = 1.0, angle: float = 0.0,
                 inertia: Optional[float] = None,
                 color=(226, 196, 118), name: str = "") -> None:
        m = density * width * height       # w 2D "gęstość" jest powierzchniowa
        if inertia is None:
            inertia = m * (width * width + height * height) / 12.0
        super().__init__(pos, angle, m, inertia, color, name)
        self.width = width
        self.height = height

    # --- punkty charakterystyczne: tym buduje się sceny ---
    def localAt(self, t: float) -> Vec2:
        """t in [-1, 1]: -1 lewy koniec, 0 środek, +1 prawy koniec (lokalnie).
        Przydatne np. do osi w proporcji 1:3 -> localAt(-0.5)."""
        return Vec2(t * 0.5 * self.width, 0.0)

    def at(self, t: float) -> Vec2:
        """Ten sam punkt, ale we współrzędnych świata."""
        return self.localToWorld(self.localAt(t))

    def end(self, sign: float = 1.0) -> Vec2:
        return self.at(sign)

    def corners(self) -> List[Vec2]:
        """Cztery wierzchołki w układzie świata, gotowe do rysowania.

        ex, ey to połowa szerokości i wysokości ("extent"): w układzie ciała
        środek masy jest w (0,0), więc wierzchołki to (+-ex, +-ey).
        Kolejność par znaków obchodzi obwód - gdyby zamienić dwie środkowe,
        pygame narysowałby kokardkę zamiast prostokąta.
        Vec2(sx*ex, sy*ey) jest STAŁE: geometria bryły sztywnej nigdy się nie
        zmienia. Cały ruch siedzi w (pos, rot) i wchodzi dopiero
        w localToWorld. Dlatego prostokąt NIE MOŻE się zdeformować - jeśli na
        ekranie wygląda na spłaszczony, to pos/rot są chore, nie kształt."""
        ex, ey = 0.5 * self.width, 0.5 * self.height
        return [self.localToWorld(Vec2(sx * ex, sy * ey))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


class Disk(Body):
    """Koło - przykład, jak dodać nowy kształt.

    Wystarczy policzyć m i I w konstruktorze; cała reszta (więzy, korekty,
    energia) działa bez zmian, bo solver widzi tylko Body.
    I = 1/2 m r^2 dla pełnego walca.
    """

    def __init__(self, pos: Vec2, radius: float, density: float = 1.0,
                 angle: float = 0.0, color=(150, 200, 250),
                 name: str = "") -> None:
        m = density * math.pi * radius * radius
        I = 0.5 * m * radius * radius
        super().__init__(pos, angle, m, I, color, name)
        self.radius = radius

    def rimPoint(self, localAngle: float = 0.0) -> Vec2:
        """Punkt na obwodzie - wygodny do zaczepiania linek (np. koło pasowe)."""
        return self.localToWorld(Vec2(self.radius, 0.0).rotate(localAngle))


class PointMass(Body):
    """Punkt materialny: I = 0, więc invInertia = 0 i obrót go nie dotyczy.

    Zasada Liskov w praktyce: wzór w = 1/m + (r x n)^2/I sam degeneruje się
    do w = 1/m, więc te same złącza łączą belkę z belką i kulkę z kulką,
    bez ani jednego 'if' w solverze.
    """

    def __init__(self, pos: Vec2, mass: float, radius: float = 0.05,
                 color=(90, 200, 255), name: str = "") -> None:
        super().__init__(pos, 0.0, mass, 0.0, color, name)
        self.invInertia = 0.0
        self.radius = radius


class CompositeBeam(Beam):
    """Belka z doczepionym punktowym obciążnikiem, traktowana jako JEDNA bryła.

    Przykład jedynego przypadku, gdy moment bezwładności trzeba policzyć
    ręcznie - twierdzenie Steinera dla ciała złożonego:

        x_c = (m_b x_b + m_o x_o) / (m_b + m_o)      wspólny środek masy
        I   = sum(I_i + m_i * d_i^2)                 d_i = odległość od x_c

    Uwaga na różnicę wobec zwykłego złączenia FixedJoint: tam mamy dwa ciała
    i solver musi w każdym podkroku pilnować spawu. Tutaj mamy jedno ciało,
    więc jest szybciej i idealnie sztywno - kosztem tego, że nie da się już
    tych części rozłączyć.
    """

    def __init__(self, pos: Vec2, width: float, height: float,
                 density: float, extraMass: float, extraAt: float,
                 angle: float = 0.0, color=(206, 176, 98),
                 name: str = "") -> None:
        mBeam = density * width * height
        xExtra = extraAt * 0.5 * width          # położenie obciążnika (lokalnie)
        mTotal = mBeam + extraMass

        xC = (mBeam * 0.0 + extraMass * xExtra) / mTotal      # środek masy
        iBeam = mBeam * (width * width + height * height) / 12.0
        I = (iBeam + mBeam * xC * xC +                        # Steiner dla belki
             extraMass * (xExtra - xC) ** 2)                  # Steiner dla masy

        # przesuwamy pos tak, żeby wskazywał wspólny środek masy
        center = pos.clone().add(Vec2(xC, 0.0).rotate(angle))
        super().__init__(center, width, height, 0.0, angle, inertia=I,
                         color=color, name=name)
        self.mass = mTotal
        self.invMass = 1.0 / mTotal
        self.inertia = I
        self.invInertia = 1.0 / I
        self.comOffset = xC          # gdzie leży środek masy względem środka belki
        self.extraLocal = Vec2(xExtra - xC, 0.0)   # gdzie siedzi obciążnik

    # UWAGA: pos wskazuje teraz WSPÓLNY środek masy, a nie środek prostokąta,
    # więc geometrię trzeba przesunąć o -comOffset, żeby rysunek zgadzał się
    # z fizyką. To dobra ilustracja tego, że w bryle sztywnej punktem
    # odniesienia jest środek masy, a nie środek kształtu.
    def localAt(self, t: float) -> Vec2:
        return Vec2(t * 0.5 * self.width - self.comOffset, 0.0)

    def corners(self) -> List[Vec2]:
        ex, ey = 0.5 * self.width, 0.5 * self.height
        return [self.localToWorld(Vec2(sx * ex - self.comOffset, sy * ey))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
