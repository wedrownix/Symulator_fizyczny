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
        self.numSteps = 1000
        self.beads = []

scene = PhysicsScene()

class Pendulum:
    def __init__(self, masses, lengths, angles):
        self.masses = masses
        self.number_objects = len(self.masses)
        self.lengths = lengths
        self.angles = angles
        self.pos = []
        self.prevPos = []
        self.vel = []
        x = 0
        y = 0
        v = Vec2()
        for l,a in zip(lengths, angles):
            x += math.sin(a) * l
            y += -math.cos(a) * l
            new_pos = v.set(x,y)
            self.pos.append(new_pos)
            self.prevPos.append(new_pos)
            self.vel.append(v)


#Funkcja, która pozwala kulce chwilowo wyjść poza ramy więzu, ale zapamiętuje jej ostatnie położenie na tym więzu
    def startStep(self,dt,gravity):
        for i in range (self.number_objects):
            self.vel[i].add(gravity, dt)
            #Prevpos jest już zapisane
            self.pos[i].add(self.vel[i], dt)

#Funkcja, która sprowadza kulkę z powrotem na więz,
    def  keepOnWire(self,center, radius):
       for i in range (self.number_objects):
           delta = Vec2().subtractVectors(self.pos[i], self.pos[i - 1])
           d = Vec2().length(delta)
           if self.masses[i] and self.masses[i - 1]:
           w0 = 1 / self.masses[i - 1]
           w1 = 1 / self.masses[i]
           corr = (self.lengths[i] - d) / d / (w0 + w1);
           self.pos[i-1].subtract(delta, w0*corr)
           self.pos[i].add(delta, w1*corr)
def endStep(self, dt):
    for i in range (self.number_objects):
        self.vel[i].subtractVectors(self.pos[i], self.prevPos[i])
        self.vel[i].scale(1/dt)




#%%SETUP SCENE

def setup_scene():
    scene.beads.clear()
    lengths = [0.2, 0.2, 0.2];
    masses = [1.0, 0.5, 0.3];
    angles = [0.5 * math.pi, math.pi, math.pi];



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


