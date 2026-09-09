"""
pbd2d/xpbd.py -- dwa wzory, przez które przechodzą WSZYSTKIE więzy.

To jest cała matematyka XPBD w projekcie. Klasy złączy nie zawierają ani
jednego wzoru - one tylko decydują, CO jest naruszone, a te dwie funkcje
liczą, o ile i komu to poprawić. Dzięki temu zmiana metody (np. dopisanie
tarcia albo powrót do klasycznego PBD) to zmiana w jednym pliku.

WZORY ZE SLAJDÓW ("Linear Correction" / "Angular Correction"):

    w_i    = m_i^-1 + ((p_i - x_i) x n)^T I_i^-1 ((p_i - x_i) x n)
    lambda = -C / (w1 + w2 + alpha/dt^2)
    x_i   <- x_i +- lambda n m_i^-1
    q_i   <- q_i +- 1/2 [lambda I_i^-1 ((p_i - x_i) x n), 0] q_i

W 2D iloczyn wektorowy jest skalarem, więc:

    w_i = 1/m_i + (r_i x n)^2 / I_i          <- getInverseMass w Body
    q_i <- q_i +- lambda I_i^-1 (r_i x n)    <- applyImpulse w Body

PBD vs XPBD: różnica to wyłącznie człon alpha/dt^2 w mianowniku.
Dla alpha = 0 (compliance = 0) oba wzory dają identyczny wynik, czyli więz
nieskończenie sztywny. Dlatego w pakiecie jest tylko XPBD - PBD jest jego
szczególnym przypadkiem.

KONWENCJA ZNAKU (jedna w całym pakiecie):
    corr = wielkość, o którą ma ZMALEĆ różnica (wartość_ciała_1 - wartość_ciała_0)
    ciało 0 dostaje korektę "+", ciało 1 korektę "-"
Ta sama umowa dotyczy pozycji, kątów i tłumienia, więc podklasy złączy nie
muszą się zastanawiać nad znakami.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from .vector2 import Vec2

if TYPE_CHECKING:                       # tylko dla podpowiedzi typów,
    from .bodies import Body            # bez importu w czasie działania


def applyLinearCorrection(corr: Vec2,
                          body0: "Body", pos0: Vec2,
                          body1: "Body", pos1: Vec2,
                          compliance: float = 0.0,
                          velocityLevel: bool = False) -> float:
    """Więz wektorowy (odległość, zaczepienie punktowe, tłumienie liniowe).

    corr        wektor naruszenia; jego długość to C, kierunek to n
    compliance  alpha [m/N] - odwrotność sztywności; 0 = więz sztywny
    velocityLevel  True -> korekta prędkości zamiast pozycji (tłumienie,
                   napędy); wtedy nie ma członu alpha, bo nie ma sprężystości

    Zwraca lambda/dt^2, czyli SIŁĘ więzu w niutonach - wartość fizyczną,
    którą można wyświetlić albo zapisać do analizy wytrzymałościowej.
    """
    C = corr.length()
    if C == 0.0:
        return 0.0
    n = corr.clone().scale(1.0 / C)

    # suma uogólnionych mas odwrotnych obu ciał: "o ile ustąpią te punkty
    # pod jednostkowym impulsem w kierunku n"
    w = body0.getInverseMass(n, pos0) + body1.getInverseMass(n, pos1)
    if w == 0.0:                       # oba ciała nieruchome - nic nie robimy
        return 0.0

    dt = body0.dt if body0.dt > 0.0 else body1.dt
    if velocityLevel:
        dl = C / w
    else:
        alpha = compliance / (dt * dt)
        dl = C / (w + alpha)

    p = n.scale(dl)                    # p = lambda * n
    body0.applyImpulse(p, pos0, velocityLevel)
    body1.applyImpulse(p.clone().scale(-1.0), pos1, velocityLevel)
    return dl / (dt * dt)


def applyAngularCorrection(corr: float,
                           body0: "Body", body1: "Body",
                           compliance: float = 0.0,
                           velocityLevel: bool = False) -> float:
    """Więz skalarny (kąt względny, ogranicznik kąta, tłumienie kątowe).

    W 2D oś obrotu jest tylko jedna, więc "wektor korekty kątowej" ze slajdu
    redukuje się do liczby, a w_i = n^T I^-1 n do samego 1/I.

    Zwraca lambda/dt^2, czyli MOMENT więzu w Nm.
    """
    if corr == 0.0:
        return 0.0
    w = body0.getInverseMass(None, None) + body1.getInverseMass(None, None)
    if w == 0.0:
        return 0.0

    dt = body0.dt if body0.dt > 0.0 else body1.dt
    if velocityLevel:
        dl = corr / w
    else:
        alpha = compliance / (dt * dt)
        dl = corr / (w + alpha)

    body0.applyTwist(dl, velocityLevel)
    body1.applyTwist(-dl, velocityLevel)
    return dl / (dt * dt)
