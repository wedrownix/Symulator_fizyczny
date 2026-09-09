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

DLACZEGO LINKI SIĘ ROZCIĄGAJĄ (najważniejsze przy strojeniu sceny)
------------------------------------------------------------------
Więz o compliance = 0 jest w teorii nierozciągliwy, ale solver jest typu
Gauss-Seidel: przechodzi po więzach po kolei, jeden po drugim. Zbieżność
takiego przechodzenia psuje się dramatycznie, gdy sąsiednie ciała mają
skrajnie różne masy - lekkie ogniwo nie jest w stanie zatrzymać ciężkiego
ładunku w jednym przejściu i lina "gumuje".

Zmierzone na scenie z ładunkiem 100 kg, lina z 5 ogniw, 40 podkroków:

    masa ogniwa      maks. rozciągnięcie liny
    0.001 kg              169 %          <- to był Twój przypadek
    0.01  kg               16 %
    0.1   kg                1.2 %
    0.5   kg                0.17 %
    2.0   kg                0.04 %

    liczba podkroków (masa ogniwa 0.01 kg):   20 -> 66 %,  40 -> 16 %,
                                             100 -> 2.4 %, 200 -> 0.55 %
    liczba iteracji  (masa ogniwa 0.01 kg):    1 -> 16 %,    2 -> 7.7 %,
                                               4 -> 3.6 %,   8 -> 1.6 %
    liczba ogniw     (masa ogniwa 1 kg):       2 -> 0.03 %, 20 -> 0.43 %

CZTERY POKRĘTŁA, w kolejności od najskuteczniejszego:

 1. nodeMass w connectRopeChain  -- REGUŁA KCIUKA: masa ogniwa nie mniejsza
    niż 1/100 masy ładunku (dla 0.1 % błędu: 1/20). Najtańsze i najskuteczniejsze.
 2. World.numSubSteps            -- błąd maleje mniej więcej jak 1/n^2,
    koszt rośnie liniowo.
 3. World.numIterations          -- dodatkowe przejścia po więzach w jednym
    podkroku; działa słabiej niż podkroki przy tym samym koszcie.
 4. numNodes                     -- każde ogniwo to kolejne "kolanko" do
    przepchnięcia informacji o sile, więc mniej ogniw = sztywniej.

Compliance zostawiamy 0.0 - dodatnia compliance rozciąga linę CELOWO
(to sprężyna) i nie jest lekarstwem na problem zbieżności.

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

from Body_finally import Body ,Beam, PointMass



# =============================================================================
# %% 5. ZŁĄCZA
# =============================================================================

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



class Joint:
    """
    ===========================================================================
    KLASA BAZOWA WSZYSTKICH ZŁĄCZY - jak to działa
    ===========================================================================

    IDEA
    ----
    Złącze nie jest obiektem fizycznym. To REGUŁA, którą solver wymusza na
    dwóch ciałach po tym, jak poleciały one swobodnie w kroku integracji.
    Każde złącze umie odpowiedzieć na dwa pytania:
        "o ile te dwa punkty się rozjechały?"   -> solvePosition()
        "o ile te dwa kąty się rozjechały?"     -> solveOrientation()
    i zlecić poprawkę. Poprawki liczą dwie funkcje globalne
    (applyLinearCorrection / applyAngularCorrection), więc sama klasa Joint
    nie zawiera ani jednego wzoru XPBD - tylko decyduje, CO ma być poprawione.

    DWA UKŁADY WSPÓŁRZĘDNYCH (slajd "Attachment Frames")
    ----------------------------------------------------
    Punkt zaczepienia podajesz RAZ, przy tworzeniu złącza, w układzie świata
    (np. "zawias jest w (0, 2.2)"). Konstruktor natychmiast przelicza go na
    współrzędne LOKALNE obu ciał (localPos0, localPos1) i tylko te zapamiętuje.

        localPos = worldToLocal(anchor)      <- raz, przy montażu
        globalPos = localToWorld(localPos)   <- co podkrok, w updateGlobalFrames

    Dzięki temu punkt zaczepienia "jeździ" razem z ciałem za darmo: gdy belka
    się obróci, jej lokalny punkt (0.9, 0) sam wyląduje w nowym miejscu świata.
    To samo dotyczy kątów: localRot to kąt ramki złącza względem własnego kąta
    ciała, a globalRot = body.rot + localRot.

    DWIE RAMKI, NIE JEDNA
    ---------------------
    Każde złącze ma DWIE ramki: jedną przyklejoną do body0, drugą do body1.
    W chwili montażu obie leżą w tym samym miejscu i mają ten sam kąt.
    Podczas symulacji rozjeżdżają się - i właśnie ten rozjazd
    (globalPos1 - globalPos0, globalRot1 - globalRot0) jest naruszeniem więzu,
    które solver kasuje. Cała reszta klasy to tylko różne sposoby mierzenia
    tego rozjazdu.

    KONWENCJA ZNAKU (jedna dla całego silnika)
    ------------------------------------------
    corr = wielkość, o którą ma ZMALEĆ różnica (wartość_ciała_1 - wartość_ciała_0).
    Ciało 0 dostaje korektę "+", ciało 1 "-". Ta sama umowa obowiązuje dla
    pozycji, kątów i tłumienia, dzięki czemu podklasy nie muszą myśleć o znakach.

    WZORZEC: METODA SZABLONOWA
    --------------------------
    solve() ma ustaloną strukturę (najpierw pozycja, potem orientacja), a to,
    CO się w tych krokach dzieje, dopisują podklasy. Klasa bazowa daje im do
    tego gotowe klocki ze slajdów Müllera:

        attach()      = Attach       - trzymaj punkty w zadanej odległości
        alignAngle()  = AlignAxes    - trzymaj zadany kąt względny
        limitAngle()  = LimitAngle   - trzymaj kąt w przedziale
        dampLinear/dampAngular       - tłumienie na poziomie prędkości

    Stąd definicje złączy są jednolinijkowe:
        linka   = attach(length, unilateral=True)
        zawias  = attach(0) [+ limitAngle(...)]
        spaw    = attach(0) + alignAngle(restAngle)
    Dodanie nowego złącza (np. suwaka) nie wymaga dotykania solvera - wystarczy
    złożyć inne klocki. To jest sens dziedziczenia po tej klasie.
    """

    def __init__(self, body0: Body, body1: Body, anchor: Vec2, frameAngle: float = 0.0):
        self.body0 = body0
        self.body1 = body1
        self.disabled = False        # True -> złącze pomijane (np. zwolnienie)

        # --- MONTAŻ: przeliczenie punktu i kąta na układy lokalne obu ciał.
        # Robione dokładnie raz. Od tej chwili złącze "trzyma się" ciał.
        self.localPos0 = body0.worldToLocal(anchor) #umieszczam w body0 na stałe mój więz - we współrzędnych lokalnych
        self.localPos1 = body1.worldToLocal(anchor)
        self.localRot0 = frameAngle - body0.rot
        self.localRot1 = frameAngle - body1.rot

        # --- bufory na aktualne (globalne) położenia ramek; odświeżane
        # w updateGlobalFrames() i czytane potem przez solver i rysowanie
        self.globalPos0 = anchor.clone()
        self.globalPos1 = anchor.clone()
        self.globalRot0 = frameAngle
        self.globalRot1 = frameAngle

        # --- diagnostyka: co ostatnio "kosztowało" utrzymanie tego złącza
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

        Normalizacja jest konieczna, bo body.rot rośnie bez ograniczeń (koło,
        które zrobiło 10 obrotów, ma rot = 62.8). Bez niej różnica kątów
        wyszłaby np. 6.2 zamiast -0.08 i spaw szarpnąłby ciałem o pełny obrót."""
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
            unilateral = True    -> więz jednostronny: działa tylko gdy
                                    odległość jest ZA DUŻA. Tak zachowuje się
                                    lina: można ją zwinąć, nie można rozciągnąć.

        Krok po kroku:
            d           wektor od punktu na ciele 0 do punktu na ciele 1
            elongation  o ile ten wektor jest dłuższy niż ma być (to jest C)
            corr        wektor o długości C, skierowany wzdłuż d -> tyle ma
                        zniknąć z różnicy (pozycja1 - pozycja0)
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
                 dt: float = 1.0 / 60.0, numSubSteps: int = 40,
                 numIterations: int = 1):
        self.gravity = gravity.clone()
        self.dt = dt
        # POKRĘTŁO nr 2: więcej podkroków = sztywniejsze więzy (błąd ~ 1/n^2),
        # koszt rośnie liniowo. To pierwsza rzecz do podkręcenia, gdy linki
        # się rozciągają, a nie da się już zwiększyć masy ogniw.
        self.numSubSteps = numSubSteps
        # POKRĘTŁO nr 3: dodatkowe przejścia po więzach WEWNĄTRZ podkroku.
        # Przy tym samym koszcie działa słabiej niż podkroki (patrz tabela
        # w nagłówku), ale bywa przydatne, gdy dt jest już bardzo małe.
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

        TU SIĘ STROI ROZCIĄGLIWOŚĆ LINY (patrz tabela w nagłówku pliku):

        nodeMass -- POKRĘTŁO nr 1, najważniejsze. Solver jest typu
            Gauss-Seidel, więc przy skrajnym stosunku mas (ogniwo 0.001 kg
            trzymające 100 kg) informacja o sile nie zdąży przejść przez
            łańcuch w jednym przejściu i lina się "gumuje". Reguła kciuka:
            masa ogniwa >= masa ładunku / 100. Poniżej jest to wymuszane
            automatycznie, z komunikatem - żeby scena nie psuła się po cichu.
            nodeMass = None -> masa dobrana sama (1/50 masy ładunku).

        numNodes -- POKRĘTŁO nr 4. Każde ogniwo to kolejne kolanko, przez
            które musi przejść siła, więc mniej ogniw = sztywniejsza lina.
            Więcej ogniw = ładniejszy zwis. 4-8 to zwykle dobry kompromis.

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

world = World(gravity=Vec2(0.0, -9.81), dt=1.0 / 60.0,
              numSubSteps=40,        # POKRĘTŁO nr 2 (sztywność wszystkich więzów)
              numIterations=1)       # POKRĘTŁO nr 3


def setup_scene() -> None:
    """Żuraw z dwoma ładunkami na linkach.

    Klocki użyte w scenie:
        Beam(density=0)  - element nieruchomy (podstawa)
        FixedJoint       - maszt i zastrzał przyspawane do podstawy
        RevoluteJoint    - wysięgnik obraca się na szczycie masztu
        connectRopeChain - dwie liny z ogniw, z ładunkami na końcach

    Masy ogniw są dobrane do mas ładunków (reguła: >= ładunek/100), inaczej
    liny gumują - patrz tabela w nagłówku pliku."""
    world.clear()

    # --- podstawa: density = 0 -> masa 0 -> ciało nieruchome
    base = world.addBeam(0.0, 0.05, 2.0, 0.10, density=0.0, color=(120, 122, 132))

    # --- maszt przyspawany do podstawy (ZŁĄCZE STAŁE)
    mast = world.addBeamBetween(Vec2(0.0, 0.10), Vec2(0.0, 2.20), 0.12,
                                density=25.0, color=(176, 138, 84))
    world.connectFixed(base, mast, Vec2(0.0, 0.10))

    # --- zastrzał: druga belka też przyspawana -> rama sztywna
    brace = world.addBeamBetween(Vec2(-0.8, 0.10), Vec2(0.0, 1.60), 0.09,
                                 density=25.0, color=(176, 138, 84))
    world.connectFixed(base, brace, Vec2(-0.8, 0.10))
    world.connectFixed(mast, brace, Vec2(0.0, 1.60))

    # --- wysięgnik na ZAWIASIE w szczycie masztu.
    # Gęstość jest duża, bo lekki wysięgnik obciążony 100 kg z jednej strony
    # natychmiast staje pionowo i uderza w ogranicznik kąta.
    boom = world.addBeam(0.5, 2.20, 1.8, 0.12, density=120.0)
    world.connectRevolute(mast, boom, Vec2(0, 2.20),
                          minAngle=-2, maxAngle=2,   # ogranicznik wychyłu
                          damping=2.0)                    # wygaszanie kołysania

    # --- lekki ładunek na długiej linie (prawa strona)
    # 1 kg, ogniwa po 0.05 kg -> stosunek 20:1, lina praktycznie nierozciągliwa
    load1 = world.addPointMass(0.9, 0.6, 1.0, 0.08, color=(90, 200, 255))
    world.connectRopeChain(boom, boom.end(1.0), load1, load1.pos.clone(),
                           numNodes=8, nodeMass=0.1)

    # --- ciężki ładunek na krótkiej linie (lewa strona)
    # 100 kg, ogniwa po 1.0 kg -> stosunek 100:1, błąd rzędu 0.1 %
    # nodeMass=None też jest poprawne: masa dobierze się sama (ładunek/50)
    load2 = world.addPointMass(-0.9, 1.90, 100.0, 0.18, color=(205, 70, 70))
    world.connectRopeChain(boom, boom.end(-1.0), load2, load2.pos.clone(),
                           numNodes=5, nodeMass=0.1 )


# =============================================================================
# %% 9. RYSOWANIE
# =============================================================================

SHOW_FORCES = False        # True -> podpisy z siłą i wydłużeniem przy złączach
fontSmall = pygame.font.SysFont("consolas", 24)


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