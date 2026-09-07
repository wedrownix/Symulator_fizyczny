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



#%%PENDULUM

class Pendulum:
    def __init__(self, masses, lengths, angles):
        self.masses = [0.0] + masses
        self.lengths = lengths
        self.angles = angles
        self.pos = []
        self.prevPos = []
        self.vel = []
        self.number_objects = len(self.masses)
        x = 0
        y = 0
        v =
        for l,a in zip(lengths, angles):
            x += math.sin(a) * l
            y += -math.cos(a) * l
            new_pos = Vec2(x,y)
            self.pos.append(new_pos)
            self.prevPos.append(new_pos)
            self.vel.append(Vec2(0,0))


    def startStep(self, dt, gravity):
        for i in range (1, self.number_objects):
            self.vel[i].add(gravity, dt)
            self.prevPos[i].set(self.pos[i])
            self.pos[i].add(self.vel[i], dt)

    def solveConstraints(self):
       for i in range (1, self.number_objects):
           delta = Vec2().subtractVectors(self.pos[i], self.pos[i - 1])
           d = delta.length()
           if d == 0.0:
               continue
               # Masy odwrotne (w = 1/m). Masa 0 = nieskończona masa (punkt stały)
           w0 = 1.0 / self.masses[i - 1] if self.masses[i - 1] > 0.0 else 0.0
           w1 = 1.0 / self.masses[i] if self.masses[i] > 0.0 else 0.0
           if w0 + w1 == 0.0:
               continue
           # Korekta pozycji w celu zachowania długości odcinka
           corr = (self.lengths[i] - d) / d / (w0 + w1)
           self.pos[i - 1].subtract(delta, w0 * corr)
           self.pos[i].add(delta, w1 * corr)

    def endStep(self, dt):
        for i in range (1, self.number_objects):
            self.vel[i].subtractVectors(self.pos[i], self.prevPos[i])
            self.vel[i].scale(1/dt)
    def draw(self, surface: pygame.Surface):
        # 1. Rysowanie prętów wahadła
        for i in range(1, self.num_segments):
            p1 = (cX(self.pos[i - 1].x), cY(self.pos[i - 1].y))
            p2 = (cX(self.pos[i].x), cY(self.pos[i].y))
            pygame.draw.line(surface, (200, 200, 200), p1, p2, 4)

        # 2. Rysowanie nieruchomego punktu zakotwiczenia
        p0 = (cX(self.pos[0].x), cY(self.pos[0].y))
        pygame.draw.circle(surface, (255, 255, 255), p0, 6)

        # 3. Rysowanie kulek
        for i in range(1, self.num_segments):
            p = (cX(self.pos[i].x), cY(self.pos[i].y))
            r = int(cScale * 0.03 * math.sqrt(self.masses[i]))
            pygame.draw.circle(surface, (0, 200, 255), p, max(r, 5))

#%%WORLD
class PhysicsScene:
    def __init__(self):
        self.gravity = Vec2(0, -10)
        self.dt = 1.0 / 60.0
        self.worldSize = Vec2(simWidth, simHeight)
        self.numSteps = 1000
        self.pendulum: Pendulum = None

scene = PhysicsScene()

#%%SETUP SCENE

def setup_scene():
    lengths = [0.25, 0.25, 0.25]
    masses = [1.0, 0.8, 0.5]
    angles = [0.5 * math.pi, math.pi, math.pi]

    scene.pendulum = Pendulum(masses, lengths, angles)

def simulate():
    if not scene.pendulum:
        return

    sdt = scene.dt / scene.numSteps

    for step in range(scene.numSteps):
        scene.pendulum.startStep(sdt, scene.gravity)
        scene.pendulum.solveConstraints()
        scene.pendulum.endStep(sdt)

def draw():
    win.fill((20, 20, 20))
    if scene.pendulum:
        scene.pendulum.draw(win)
    pygame.display.update()



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

def draw():
    win.fill((255, 255, 255))


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


