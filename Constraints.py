import math
import Vector2 as Vec2
import pygame
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
        self.bead = None

scene = PhysicsScene()

class Bead:
    def __init__(self, radius, mass, pos):
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.prevPos = pos.clone()
        self.vel = Vec2()

#Funkcja
    def startStep(self,dt,gravity):
        self.vel.add(gravity,dt)
        self.prevPos.set(self.pos)
        self.pos.add(self.vel, dt)

    def  keepOnWire(self,center, radius):
        dir = Vec2()
        dir.subtractVectors(self.pos, center)
        d = dir.length()
        if d == 0:
            return
        dir.scale(1/d)
        lam = PhysicsScene.wireRadius - d
        self.pos.add(dir, lam)

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


