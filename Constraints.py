import math
import Vector2 as Vec2
import pygame
import random
pygame.init()
from typing import List

#%%TWORZENIE OKNA,
screen_width = 1000
screen_height = 700
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Nauka_Symulatora")
clock = pygame.time.Clock()


simMinWidth = 20 #definiuje minimalną odległość obserwowaną na ekranie
cScale = min(screen_width,screen_height)/simMinWidth
simWidth = screen_width/cScale
simHeight = screen_height/cScale

def cX(x):
    return x *cScale
def cY(y):
    return screen_height - y *cScale



#%%WORLD
class PhysicsScene:
    def __init__(self):
        self.gravity = Vec2(0, -10)
        self.dt = 1.0 / 60.0
        self.worldSize = Vec2(simWidth, simHeight)
        self.wireCenter = Vec2()
        self.wireRadius = 0.0
        self.numSteps = 100
        self.beads = []

scene = PhysicsScene()

class Bead:
    def __init__(self, radius, mass, pos):
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.prevPos = pos.clone()
        self.vel = Vec2()

#Funkcja, która pozwala kulce chwilowo wyjść poza ramy więzu, ale zapamiętuje jej ostatnie położenie na tym więzu
    def startStep(self,dt,gravity):
        self.vel.add(gravity,dt)
        self.prevPos.set(self.pos)
        self.pos.add(self.vel, dt)

#Funkcja, która sprowadza kulkę z powrotem na więz,
    def  keepOnWire(self,center, radius):
        dir = Vec2()
        dir.subtractVectors(self.pos, center)
        d = dir.length()
        if d == 0:
            return
        dir.scale(1/d)
        lam = PhysicsScene.wireRadius - d
        self.pos.add(dir, lam)

    def endStep(self, dt):
        self.vel.subtractVectors(self.pos, self.prevPos)
        self.vel.scale(1/dt)



#%%COLISIONS
def handle_ball_ball_collision(b1: Bead, b2: Bead):
    #Badam różnicę między odległościami
    dir = Vec2().subtractVectors(b2.pos, b1.pos)
    d = dir.length()

    if d == 0 or d > b1.radius + b2.radius: #d==0, to wtedy jesli wylosuję kolizję tej samej kulki ze sobą
        return
    #Należy skorygować położenie kul
    dir.scale(1.0 / d) #skaluję wektor różnicy położeń obu obiektów, tak by dostać wektor kierunkowy

    corr = (b1.radius + b2.radius - d) / 2.0 #Ponieważ kule są bliżej niż jest to fizycznie możliwe to je muszę rozdzielić po równo. corr to połowa oległości na jaką się nakładają te obiekty
    b1.pos.add(dir, -corr) #dodaję połowę odległości nakładania się obiektów w kierunku osi zderzenia
    b2.pos.add(dir, corr)

    v1 = b1.vel.dot(dir) #Ustalam prędkość wzdłuż osi zderzenia - rzut prędkości całkowitej na oś zderzenia
    v2 = b2.vel.dot(dir)

    m1 = b1.mass
    m2 = b2.mass
    #Parametr zderzenia
    r1 = b1.restitution
    r2 = b2.restitution
    #Wynik kolizji
    newV1 = (m1*v1 + m2*v2 - m2*(v1 - v2)*r1) / (m1 + m2)
    newV2 = (m1*v1 + m2*v2 - m1*(v2 - v1)*r2) / (m1 + m2)

    b1.vel.add(dir, newV1 - v1)
    b2.vel.add(dir, newV2 - v2)

#%%SETUP SCENE

def setup_scene():
    PhysicsScene.wireCenter.x = simWidth / 2.0
    PhysicsScene.wireCenter.y = simHeight / 2.0
    PhysicsScene.wireRadius = simMinWidth * 0.4

    num_beads = 5
    r = 0.1
    angle = 0.0

    for i in range(num_beads):
        mass = math.pi * r * r
        pos = Vec2(
            scene.wireCenter.x + scene.wireRadius * math.cos(angle),
            scene.wireCenter.y + scene.wireRadius * math.sin(angle)
        )
        scene.beads.append(Bead(r, mass, pos))
        angle += math.pi / num_beads
        r = 0.05 + random.random() * 0.1

#%% Symulacja i rysowanie

def simulate():
    sdt = scene.dt / scene.numSteps
    for step in range(scene.numSteps):
        #Na początek grawitacja
        for bead in scene.beads:
            bead.startStep(sdt, scene.gravity)
        #Teraz sprowadzam na drut
        for bead in scene.beads:
            bead.keepOnWire(scene.wireCenter, scene.wireRadius)
        #Na koniec wyznaczam nową prędkość
        for bead in scene.beads:
            bead.endStep(sdt)
        #Kolizje
        for i in range(len(scene.beads)):
            for j in range(i):
                handle_bead_bead_collision(scene.beads[i], scene.beads[j])


#%%MAIN LOOP

setup_scene()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    simulate()
    draw()

    clock.tick(60)

pygame.quit()


