"""
World_finally.py -- WARSTWA 4: świat symulacji.

Zawiera klasę World: listy ciał i złączy, pętlę czasową oraz metody
"klocków lego" (addBeam, connectRope, connectRopeChain...).

Zależy od Body_finally i Joint_finally. Nadal ZERO pygame - świat da się
policzyć bez otwierania okna (przydatne przy badaniu parametrów w pętli).

NOWE względem Twojej wersji (dwie krótkie metody, nic więcej):
    releaseBody(body)   wyłącza wszystkie więzy dotyczące danego ciała
    releaseJoint(joint) wyłącza pojedynczy więz
To jest cała obsługa "przecięcia liny" w trakcie symulacji.
"""

import math
from typing import List, Optional

from Vector2_finally import Vec2
from Body_finally import Body, Beam, PointMass
from Joint_finally import Joint, RopeJoint, RevoluteJoint, FixedJoint


class World:
    """
    Pętla ze slajdu "XPBD Algorithm for Rigid Bodies" + "Velocity Step":

        for n sub-steps:
            for all bodies:      integrate v, x, omega, q
            for all joints:      solve()
            for all bodies:      update v, omega
            for all joints:      solveVelocity()   (tłumienie)

    Sub-stepping: n MAŁYCH pełnych kroków zbiega znacznie lepiej niż
    n iteracji solvera w jednym dużym kroku, przy tym samym koszcie.
    Dlatego numSubSteps jest duże, a numIterations = 1.
    """

    def __init__(self, gravity: Vec2 = Vec2(0.0, -9.81),
                 dt: float = 1.0 / 60.0, numSubSteps: int = 40,
                 numIterations: int = 1):
        self.gravity = gravity.clone()
        self.dt = dt
        # POKRĘTŁO nr 2: więcej podkroków = sztywniejsze więzy (błąd ~ 1/n^2),
        # koszt rośnie liniowo.
        self.numSubSteps = numSubSteps
        # POKRĘTŁO nr 3: dodatkowe przejścia po więzach WEWNĄTRZ podkroku;
        # przy tym samym koszcie działa słabiej niż podkroki.
        self.numIterations = numIterations
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
                         numNodes: int = 4, nodeMass: Optional[float] = None,
                         length: Optional[float] = None,
                         compliance: float = 0.0) -> List[PointMass]:
        """Lina z ogniw: b0 --o--o--o--o-- b1. Zamiast jednego więzu robimy
        łańcuch mas punktowych, dzięki czemu lina naprawdę zwisa i faluje.

        TU SIĘ STROI ROZCIĄGLIWOŚĆ LINY:

        nodeMass -- POKRĘTŁO nr 1, najważniejsze. Solver jest typu
            Gauss-Seidel, więc przy skrajnym stosunku mas (ogniwo 0.001 kg
            trzymające 100 kg) informacja o sile nie zdąży przejść przez
            łańcuch w jednym przejściu i lina się "gumuje". Reguła kciuka:
            masa ogniwa >= masa ładunku / 100. Poniżej jest to wymuszane
            automatycznie, z komunikatem.
            nodeMass = None -> masa dobrana sama (1/50 masy ładunku).

        numNodes -- POKRĘTŁO nr 4. Mniej ogniw = sztywniejsza lina,
            więcej ogniw = ładniejszy zwis. 4-8 to zwykle dobry kompromis.

        compliance -- zostawiamy 0.0. Dodatnia compliance to CELOWA
            sprężystość liny (w m/N), a nie lekarstwo na złą zbieżność.
        """
        # --- dobór masy ogniwa i zabezpieczenie przed skrajnym stosunkiem mas
        loadMass = b1.mass if b1.mass > 0.0 else b0.mass
        if nodeMass is None:
            nodeMass = max(loadMass / 50.0, 1e-3)
        minMass = loadMass / 100.0
        if loadMass > 0.0 and nodeMass < minMass:
            print(f"[lina] masa ogniwa {nodeMass:g} kg jest za mała wobec "
                  f"ładunku {loadMass:g} kg - podnoszę do {minMass:g} kg "
                  f"(inaczej lina będzie się rozciągać)")
            nodeMass = minMass

        # --- właściwa budowa liny
        if length is None:
            length = Vec2().subtractVectors(anchor1, anchor0).length()
        seg = length / (numNodes + 1)          # długość pojedynczego ogniwa

        # kierunek, wzdłuż którego rozkładamy ogniwa na starcie; dzięki temu
        # w chwili t = 0 żaden więz nie jest naruszony i nie ma "szarpnięcia"
        direction = Vec2().subtractVectors(anchor1, anchor0)
        dl = direction.length()
        direction.scale(1.0 / dl if dl > 0.0 else 0.0)

        nodes: List[PointMass] = []
        prevBody, prevPoint = b0, anchor0
        for i in range(numNodes):
            p = anchor0.clone().add(direction, seg * (i + 1))
            node = self.addPointMass(p.x, p.y, nodeMass, 0.03,
                                     color=(225, 225, 225))
            self.connectRope(prevBody, node, prevPoint, p, length=seg,
                             compliance=compliance)
            nodes.append(node)
            prevBody, prevPoint = node, p
        # ostatnie ogniwo domyka łańcuch do ciała docelowego
        self.connectRope(prevBody, b1, prevPoint, anchor1, length=seg,
                         compliance=compliance)
        return nodes

    def _add(self, obj):
        (self.joints if isinstance(obj, Joint) else self.bodies).append(obj)
        return obj

    # ---- ZWALNIANIE WIĘZÓW ----------------------------------------------
    def releaseBody(self, body: Body) -> int:
        """Zwalnia ciało: wyłącza WSZYSTKIE więzy, w których ono występuje.

        Nie usuwamy złącza z listy, tylko ustawiamy disabled = True. Solver
        pomija je w solve() i solveVelocity(), a rysowanie może je pokazać
        innym kolorem. Zwraca liczbę zwolnionych więzów (0 = nic nie znaleziono,
        np. bo ciało już wcześniej zwolniono)."""
        n = 0
        for j in self.joints:
            if (j.body0 is body or j.body1 is body) and not j.disabled:
                j.disabled = True
                n += 1
        return n

    def releaseJoint(self, joint: Joint) -> None:
        """Zwalnia pojedynczy więz."""
        joint.disabled = True

    # ---- symulacja ------------------------------------------------------
    def simulate(self) -> None:
        sdt = self.dt / self.numSubSteps
        for _ in range(self.numSubSteps):
            for b in self.bodies:
                b.integrate(sdt, self.gravity)
            for _ in range(self.numIterations):
                for j in self.joints:
                    j.solve()
            for b in self.bodies:
                b.updateVelocities()
            for j in self.joints:
                if not j.disabled:
                    j.solveVelocity(sdt)

    def totalKineticEnergy(self) -> float:
        return sum(b.kineticEnergy() for b in self.bodies)
