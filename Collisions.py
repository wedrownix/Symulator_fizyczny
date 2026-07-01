import math

import pygame
pygame.init()
import numpy as np

#TWORZENIE OKNA,
screen_width = 500
screen_height = 480
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Nauka_Symulatora")


simMinWidth = 20 #definiuje minimalną odległość obserwowaną na ekranie
cScale = min(screen_width,screen_height)/simMinWidth
simWidth = screen_width/cScale
simHeight = screen_height/cScale

def cX(x):
    return x *cScale
def cY(y):
    return screen_height - y *cScale

#Vector Math
class Vector2():
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def set(self,w):
        self.x = w[0]
        self.y = w[1]

    def clone(self):
        return Vector2(self.x,self.y)

    def add(self,w,s = 1):
        self.x += w[0] * s
        self.y += w[1] * s
        return self

    def addVectors(self, a, b):
        self.x = a.x + b.x
        self.y = a.y + b.y
        return self

    def subtract(self,w, s = 1):
        self.x -= w[0] *s
        self.y -= w[1] *s
        return self

    def subtractVectors(self, a, b):
        self.x = a.x - b.x
        self.y = a.y - b.y
        return self

    def length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def scale(self, s):
        self.x *= s
        self.y *= s

    def dot(self, w):
        return (self.x*w[0]) + (self.y*w[1])

class Ball:
    def __init__(self, radius, mass, pos, vel):
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.vel = vel.clone()

    def simulate(self, dt, gravity):
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)

class PhysicsScene:
    def __init__(self):
        self.gravity = Vector2(0.0, 0.0)
        self.dt = 1.0 / 60.0
        self.worldSize = Vector2(2.0, 2.0)
        self.balls = []
        self.restitution = 1.0


scene = PhysicsScene()

#MAIN LOOP
clock = pygame.time.Clock()
run = True
while run:

    # Komendy od użytkownika - tzw. "events" czyli UP, DOWN, SPACEBAR itd.
    win.fill((30, 30, 30))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    # Logika gry
    simulate()

    # Rysowanie elementów
    pygame.draw.circle(win, (255,0,0), (cX(ball.x), cY(ball.y)), ball.radius*cScale)
    pygame.display.update()

    # kontrolowanie czasu
    clock.tick(60)
pygame.quit()





