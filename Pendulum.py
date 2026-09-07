import math
from Vector2 import Vec2
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
        self.numSteps = 1000
        self.beads = []

scene = PhysicsScene()

class Bead:
    def __init__(self, radius, mass, pos):
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.prevPos = pos.clone()
        self.vel = Vec2()
        self.restitution = 1.0

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
        lam = radius - d
        self.pos.add(dir, lam)

    def endStep(self, dt):
        self.vel.subtractVectors(self.pos, self.prevPos)
        self.vel.scale(1/dt)




#%%SETUP SCENE

def setup_scene():
    scene.beads.clear()
    scene.wireCenter.x = simWidth / 2.0
    scene.wireCenter.y = simHeight / 2.0
    scene.wireRadius = simMinWidth * 0.4

    num_beads = 5
    r = 1
    angle = 0.0

    for i in range(num_beads):
        mass = math.pi * r * r
        pos = Vec2(
            scene.wireCenter.x + scene.wireRadius * math.cos(angle),
            scene.wireCenter.y + scene.wireRadius * math.sin(angle)
        )
        scene.beads.append(Bead(r, mass, pos))
        angle += math.pi / num_beads
        r = 0.75 + random.random() * 0.5

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
                handle_ball_ball_collision(scene.beads[i], scene.beads[j])

def draw():
    win.fill((255, 255, 255))

    # Rysowanie okręgu (drutu/więzu) - okrąg pusty w środku (width=2)
    wire_center_px = (cX(scene.wireCenter.x), cY(scene.wireCenter.y))
    wire_radius_px = int(scene.wireRadius * cScale)
    pygame.draw.circle(win, (255, 0, 0), wire_center_px, wire_radius_px, width=2)

    # Rysowanie kulek
    for bead in scene.beads:
        bead_center_px = (cX(bead.pos.x), cY(bead.pos.y))
        bead_radius_px = int(bead.radius * cScale)
        pygame.draw.circle(win, (255, 0, 0), bead_center_px, bead_radius_px)

    pygame.display.update()






#%%MAIN LOOP

setup_scene()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:  # restart symulacji
                setup_scene()


    simulate()
    draw()

    clock.tick(60)

pygame.quit()


