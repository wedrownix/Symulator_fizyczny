"""
scenes/machines.py -- scena pokazowa: nowe złącza i nowe kształty.

Nie ma tu nowej fizyki, tylko demonstracja, że rozbudowa silnika sprowadza
się do składania istniejących klocków:

    MotorJoint      napędzana korba (Disk) -> korbowód -> suwak
    PrismaticJoint  suwak w prowadnicy
    SpringJoint     zawieszenie sprężynowe
    CompositeBeam   belka z obciążnikiem jako JEDNA bryła
    Disk            koło zamachowe

Klawisze zwalniania (main.py) działają tu tak samo - liny mają etykiety.
"""

from __future__ import annotations
import math

from pbd2d import Vec2, World, SceneBuilder


def build(world: World) -> SceneBuilder:
    world.clear()
    b = SceneBuilder(world)

    ground = b.beam("grunt", 0.0, 0.05, 6.0, 0.10, density=0.0,
                    color=(120, 122, 132))

    # ---------------------------------------------------------------- 1
    # MECHANIZM KORBOWY: motor -> korba (koło) -> korbowód -> suwak
    # ---------------------------------------------------------------- 
    hub = Vec2(-1.6, 1.2)
    post = b.beamBetween("slup", Vec2(-1.6, 0.10), hub, 0.10, 25.0,
                         color=(176, 138, 84))
    b.fixed(ground, post, Vec2(-1.6, 0.10))

    crank = b.disk("korba", hub.x, hub.y, 0.22, density=30.0)
    b.motor(post, crank, hub, velocity=3.0, tag="motor")   # napęd 3 rad/s

    # korbowód: pręt (unilateral = False) od obwodu korby do suwaka
    pin = crank.rimPoint(0.0)                     # czop na obwodzie koła
    slider = b.beam("suwak", -0.2, 1.2, 0.30, 0.16, density=20.0,
                    color=(150, 200, 150))
    b.rope(crank, slider, pin, slider.end(-1.0), unilateral=False, damping=0.5)

    # prowadnica suwaka: PrismaticJoint pozwala tylko na ruch poziomy
    rail = b.beam("prowadnica", -0.2, 1.2, 1.4, 0.04, density=0.0,
                  color=(90, 92, 100))
    b.prismatic(rail, slider, slider.pos.clone(), axisAngle=0.0,
                minP=-0.5, maxP=0.5, damping=0.5)

    # ---------------------------------------------------------------- 2
    # ZAWIESZENIE SPRĘŻYNOWE: masa na sprężynie o zadanej sztywności
    # ----------------------------------------------------------------
    hook = Vec2(0.9, 1.9)
    gantry = b.beamBetween("brama", Vec2(0.9, 0.10), hook, 0.10, 25.0,
                           color=(176, 138, 84))
    b.fixed(ground, gantry, Vec2(0.9, 0.10))

    load = b.pointMass("masa_spr", 0.9, 1.2, 8.0, 0.12, color=(255, 170, 90))
    # k = 800 N/m -> statyczne ugięcie 8*9.81/800 = ok. 10 cm
    b.spring(gantry, load, hook, load.pos.clone(), stiffness=800.0, damping=2.0)

    # ---------------------------------------------------------------- 3
    # CIAŁO ZŁOŻONE: belka z obciążnikiem na końcu, jako JEDNA bryła.
    # Wisi na zawiasie - widać, że wychyla się inaczej niż belka jednorodna,
    # bo środek masy i moment bezwładności są przesunięte.
    # ----------------------------------------------------------------
    pivot = Vec2(2.4, 1.9)
    mastR = b.beamBetween("slup2", Vec2(2.4, 0.10), pivot, 0.10, 25.0,
                          color=(176, 138, 84))
    b.fixed(ground, mastR, Vec2(2.4, 0.10))

    lever = b.compositeBeam("dzwignia", pivot.x + 0.0, pivot.y, 1.0, 0.06,
                            density=10.0, extraMass=4.0, extraAt=1.0,
                            color=(206, 176, 98))
    # zaczepiamy za lewy koniec belki (localAt(-1) uwzględnia offset środka masy)
    b.revolute(mastR, lever, lever.end(-1.0), damping=0.3, tag="dzwignia")

    # ---------------------------------------------------------------- 4
    # LINA Z OGNIW z etykietą - do przetestowania zwalniania klawiszem
    # ----------------------------------------------------------------
    ball = b.pointMass("kulka", 2.9, 0.9, 3.0, 0.12, color=(90, 200, 255))
    b.ropeChain(lever, lever.end(1.0), ball, ball.pos.clone(),
                numNodes=5, nodeMass=0.15, tag="lina", namePrefix="l")

    return b
