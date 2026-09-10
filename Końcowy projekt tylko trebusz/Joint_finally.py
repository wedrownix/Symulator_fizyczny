"""
Joint_finally.py -- WARSTWA 3: złącza między bryłami.

Zawiera dokładnie to, co miałeś: Joint, RopeJoint, RevoluteJoint, FixedJoint.
Zależy tylko od Vector2_finally i Body_finally (w dół, nigdy w górę) - nie wie
nic o World ani o pygame.

===========================================================================
 KLASA BAZOWA Joint - jak to działa
===========================================================================

IDEA
    Złącze nie jest obiektem fizycznym. To REGUŁA, którą solver wymusza na
    dwóch ciałach po tym, jak poleciały swobodnie w kroku integracji.
    Każde złącze odpowiada na dwa pytania:
        "o ile rozjechały się punkty?"  -> solvePosition()
        "o ile rozjechały się kąty?"    -> solveOrientation()
    i zleca poprawkę. Matematykę liczą applyLinearCorrection /
    applyAngularCorrection z Body_finally, więc w tej klasie NIE MA ani
    jednego wzoru XPBD - jest tylko decyzja, CO poprawić.

DWA UKŁADY WSPÓŁRZĘDNYCH
    Punkt zaczepienia podajesz RAZ, w układzie świata ("zawias w (0, 2.2)").
    Konstruktor przelicza go na współrzędne LOKALNE obu ciał i tylko te
    zapamiętuje:
        localPos  = worldToLocal(anchor)      <- raz, przy montażu
        globalPos = localToWorld(localPos)    <- co podkrok
    Dzięki temu punkt jeździ razem z ciałem za darmo.

DWIE RAMKI, NIE JEDNA
    Każde złącze ma dwie ramki: jedną przyklejoną do body0, drugą do body1.
    Przy montażu leżą w tym samym miejscu i mają ten sam kąt. Podczas
    symulacji rozjeżdżają się - i ten rozjazd JEST naruszeniem więzu.

WZORZEC: METODA SZABLONOWA
    solve() ma stały scenariusz, treść kroków dopisują podklasy z gotowych
    klocków: attach(), alignAngle(), limitAngle(), dampLinear/dampAngular.
        linka  = attach(length, unilateral=True)
        zawias = attach(0) [+ limitAngle(...)]
        spaw   = attach(0) + alignAngle(restAngle)
"""

import math
from typing import Optional

from Vector2_finally import Vec2, normalizeAngle
from Body_finally import (Body, applyLinearCorrection, applyAngularCorrection)


class Joint:
    """Klasa bazowa wszystkich złączy - patrz opis na górze pliku."""

    def __init__(self, body0: Body, body1: Body, anchor: Vec2,
                 frameAngle: float = 0.0):
        """
        anchor      punkt zaczepienia w układzie ŚWIATA (metry)
        frameAngle  kąt ZERA ramek złącza, też w układzie świata [rad].

        CO TO JEST frameAngle
        ---------------------
        Oprócz punktu, złącze ma własny "układ odniesienia kąta" - kierunek,
        który uznaje za zero. frameAngle mówi, jak ten kierunek jest ustawiony
        w świecie w chwili montażu. Z niego liczone są localRot0 i localRot1:
        o ile kąt każdego z ciał różni się od kąta ramki.

        Praktycznie: w TYCH trzech złączach frameAngle nie wpływa na wynik,
        bo skraca się w odejmowaniu (patrz relativeAngle poniżej). Ma znaczenie
        dopiero wtedy, gdy złącze potrzebuje KIERUNKU, a nie tylko różnicy
        kątów - np. suwak, który musi wiedzieć, wzdłuż której osi wolno się
        przesuwać. Dlatego zostawiamy go w konstruktorze jako 0.0: to miejsce
        przygotowane pod rozbudowę.
        """
        self.body0 = body0
        self.body1 = body1
        self.disabled = False        # True -> złącze pomijane (np. zwolnienie)

        # --- MONTAŻ: przeliczenie punktu i kąta na układy lokalne obu ciał.
        # Robione dokładnie raz. Od tej chwili złącze "trzyma się" ciał.
        self.localPos0 = body0.worldToLocal(anchor)
        self.localPos1 = body1.worldToLocal(anchor)
        self.localRot0 = frameAngle - body0.rot
        self.localRot1 = frameAngle - body1.rot

        # --- bufory na aktualne (globalne) położenia ramek; odświeżane
        # w updateGlobalFrames() i czytane potem przez solver i rysowanie
        self.globalPos0 = anchor.clone()
        self.globalPos1 = anchor.clone()
        self.globalRot0 = frameAngle
        self.globalRot1 = frameAngle

        # --- DIAGNOSTYKA: co ostatnio "kosztowało" utrzymanie tego złącza.
        # Te trzy pola NIE BIORĄ UDZIAŁU w symulacji - nikt ich nie czyta
        # w kolejnym kroku. To wyłącznie zapis ostatniego wyniku, do
        # wyświetlania i do analizy wytrzymałościowej.
        #   force       lambda/dt^2 zwrócone przez applyLinearCorrection.
        #               Fizycznie: siła, jaką więz musiał zadziałać, żeby
        #               utrzymać ciała razem. Dla liny luźnej ustawiane na 0.
        #   torque      to samo dla korekty kątowej (moment w Nm).
        #   elongation  o ile punkty były dalej od siebie, niż powinny.
        #               Dla sztywnego więzu to ułamki milimetra; rosnące
        #               wartości = solver nie nadąża (za mało podkroków).
        self.force = 0.0          # siła więzu [N]   = lambda/dt^2
        self.torque = 0.0         # moment więzu [Nm]
        self.elongation = 0.0     # rozjazd punktów ponad długość spoczynkową [m]

    def updateGlobalFrames(self) -> None:
        """Gdzie SĄ TERAZ obie ramki zaczepienia.

        Wołane na początku każdego klocka (attach/alignAngle/limitAngle), a nie
        raz na podkrok - i to jest celowe: klocki wykonują się po kolei, każdy
        zmienia pozycje ciał, więc drugi klocek musi patrzeć na stan już
        poprawiony przez pierwszy. To jest istota metody Gaussa-Seidla."""
        self.globalPos0 = self.body0.localToWorld(self.localPos0)
        self.globalPos1 = self.body1.localToWorld(self.localPos1)
        self.globalRot0 = self.body0.rot + self.localRot0
        self.globalRot1 = self.body1.rot + self.localRot1

    def relativeAngle(self) -> float:
        """Kąt między ramkami, sprowadzony do (-pi, pi].

        Tu widać, dlaczego frameAngle się skraca:
            globalRot1 - globalRot0
          = (rot1 + frameAngle - rot1_montaz) - (rot0 + frameAngle - rot0_montaz)
          = (rot1 - rot1_montaz) - (rot0 - rot0_montaz)
        Zostaje sama informacja "o ile każde ciało obróciło się od montażu",
        a wspólne zero wypada. Dlatego dla zawiasu i spawu można podać
        dowolny frameAngle - wynik będzie ten sam."""
        return normalizeAngle(self.globalRot1 - self.globalRot0)

    # ---- szablon --------------------------------------------------------
    def solve(self) -> None:
        """METODA SZABLONOWA: stały scenariusz, zmienna treść.

        Kolejność ma znaczenie: najpierw ustawiamy punkty (pozycja), potem
        kąty (orientacja). Odwrotna kolejność też by działała, ale zbiegałaby
        wolniej - poprawka kątowa przesuwa punkty zaczepienia, więc lepiej
        żeby to ona była ostatnia."""
        if self.disabled:
            return
        self.solvePosition()
        self.solveOrientation()

    def solvePosition(self) -> None:
        """Do nadpisania: więzy na POŁOŻENIE punktów zaczepienia."""
        pass

    def solveOrientation(self) -> None:
        """Do nadpisania: więzy na KĄT względny ciał."""
        pass

    def solveVelocity(self, dt: float) -> None:
        """Do nadpisania: korekty na POZIOMIE PRĘDKOŚCI (tłumienie, napędy).
        Wołane po updateVelocities, czyli gdy prędkości są już policzone."""
        pass

    # ---- klocki (Building Blocks ze slajdów) ----------------------------
    def attach(self, restDistance: float = 0.0, compliance: float = 0.0,
               unilateral: bool = False) -> None:
        """Attach(p1, p2, d_rest, alpha) - trzyma punkty zaczepienia
        w odległości restDistance.

            restDistance = 0     -> punkty mają się pokrywać (zawias, spaw)
            restDistance = L     -> odległość dokładnie L (pręt, linka)

            unilateral: bool = False
                'bool' to typ logiczny: wartość może być tylko True albo False.
                '= False' to wartość DOMYŚLNA - jeśli wywołasz attach() bez tego
                argumentu, Python podstawi False.
                Znaczenie: więz JEDNOSTRONNY (łac. unilateralis - jednostronny).
                    False -> więz dwustronny: pilnuje odległości w OBIE strony,
                             czyli nie pozwala ani się oddalić, ani zbliżyć.
                             To zachowanie sztywnego PRĘTA.
                    True  -> więz jednostronny: reaguje TYLKO gdy odległość
                             jest za duża. Można się zbliżyć do woli.
                             To zachowanie LINY - można ją zwinąć, nie można
                             rozciągnąć.
                W kodzie realizuje to jeden warunek: gdy elongation < 0
                (punkty bliżej niż długość liny), funkcja po prostu wychodzi
                bez korekty i zeruje force - lina jest luźna, nie ciągnie.

        Krok po kroku:
            d           wektor od punktu na ciele 0 do punktu na ciele 1
            elongation  o ile ten wektor jest dłuższy niż ma być (to jest C)
            corr        wektor o długości C, skierowany wzdłuż d
        """
        self.updateGlobalFrames()
        d = Vec2().subtractVectors(self.globalPos1, self.globalPos0)
        dist = d.length()
        if dist == 0.0:
            return                      # punkty się pokrywają - nie ma kierunku
        self.elongation = dist - restDistance
        if unilateral and self.elongation < 0.0:
            self.force = 0.0            # lina luźna - żadnej siły
            return
        corr = d.scale(self.elongation / dist)
        self.force = applyLinearCorrection(corr, self.body0, self.globalPos0,
                                           self.body1, self.globalPos1,
                                           compliance)

    def alignAngle(self, targetAngle: float = 0.0, compliance: float = 0.0) -> None:
        """AlignAxes(a1, a2, alpha) - wymusza zadany kąt względny ramek.

        W 3D trzeba do tego iloczynu wektorowego dwóch osi (a1 x a2), bo osi
        obrotu jest wiele. W 2D oś jest jedna, więc "kąt względny" to zwykła
        liczba i cały więz sprowadza się do odejmowania.

        targetAngle = 0 oznacza "obie ramki mają ten sam kąt", czyli spaw.
        Uwaga: FixedJoint podaje tu restAngle zapamiętany przy montażu, żeby
        nie prostować na siłę belek, które zostały zbudowane pod kątem."""
        self.updateGlobalFrames()
        corr = normalizeAngle(self.relativeAngle() - targetAngle)
        self.torque = applyAngularCorrection(corr, self.body0, self.body1,
                                             compliance)

    def limitAngle(self, minAngle: float, maxAngle: float,
                   compliance: float = 0.0) -> None:
        """LimitAngle(n, a1, a2, min, max, alpha) - ogranicznik zakresu.

        Wewnątrz przedziału NIE ROBI NIC (zawias jest swobodny), a po jego
        przekroczeniu popycha z powrotem dokładnie do krawędzi. To jest więz
        jednostronny, kątowy odpowiednik liny.

        Sztuczka: ustawienie minAngle = maxAngle = fi zamienia ogranicznik
        w serwo, które trzyma zadany kąt. Tak właśnie na slajdach Müllera
        z tego samego klocka powstają Hinge, Servo i Motor."""
        self.updateGlobalFrames()
        phi = self.relativeAngle()
        if minAngle <= phi <= maxAngle:
            return
        phiClamped = max(minAngle, min(phi, maxAngle))
        self.torque = applyAngularCorrection(normalizeAngle(phi - phiClamped),
                                             self.body0, self.body1, compliance)

    def dampAngular(self, dt: float, coeff: float) -> None:
        """DampAngular ze slajdu - zbliża prędkości kątowe obu ciał.

        Nie jest to tarcie w przegubie w sensie fizycznym, tylko wygaszanie
        drgań. Mnożnik min(coeff*dt, 1) gwarantuje, że nigdy nie odejmiemy
        więcej niż całą różnicę prędkości - inaczej tłumienie zaczęłoby
        rozkręcać układ w drugą stronę."""
        if coeff <= 0.0:
            return
        corr = (self.body1.omega - self.body0.omega) * min(coeff * dt, 1.0)
        applyAngularCorrection(corr, self.body0, self.body1, 0.0, velocityLevel=True)

    def dampLinear(self, dt: float, coeff: float) -> None:
        """DampLinear ze slajdu - tłumi względny ruch punktów zaczepienia.

        velocityAt() liczy prędkość PUNKTU ciała (v + omega x r), a nie
        środka masy - bo to punkt zaczepienia jest tym, co ma przestać drgać.
        Przydatne na linkach: bez tego łańcuch ogniw drga w nieskończoność."""
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
                 unilateral: bool = True, damping: float = 0.0):
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
        # trzymam punkty w odległości self.length; kątów nie ruszam,
        # bo lina nie przenosi momentu - stąd brak solveOrientation
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
