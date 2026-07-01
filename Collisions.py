import math
import random
import pygame
pygame.init()
import numpy as np

#%%TWORZENIE OKNA,
screen_width = 1000
screen_height = 700
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

#%%Vector Math
class Vector2:
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

#%%OBJECT - BALL
class Ball:
    def __init__(self, radius, mass, pos, vel):
        self.radius = radius
        self.mass = mass
        self.pos = pos.clone()
        self.vel = vel.clone()

    def simulate(self, dt, gravity):
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)

#%%WORLD
class PhysicsScene:
    def __init__(self):
        self.gravity = Vector2(0.0, 0.0)
        self.dt = 1.0 / 60.0
        self.worldSize = Vector2(simWidth, simHeight)
        self.balls = []
        self.restitution = 1.0

scene = PhysicsScene()

#%%SET UP

def setup_scene():
    scene.balls = []

    numBalls = 15

    for _ in range(numBalls):
        radius = 0.05 + random.random() * 0.1
        mass = math.pi * radius * radius

        pos = Vector2(
            random.random() * scene.worldSize.x,
            random.random() * scene.worldSize.y
        )

        vel = Vector2(
            -1.0 + 2.0 * random.random(),
            -1.0 + 2.0 * random.random()
        )

        scene.balls.append(Ball(radius, mass, pos, vel))

#%% COLISSIONS
def handle_ball_collision(b1: Vector2, b2: Vector2):
    #Badam różnicę między odległościami
    dir = Vector2().subtractVectors(b2.pos, b1.pos)
    d = dir.length()

    if d == 0 or d > b1.radius + b2.radius:
        return
    #Należy skorygować położenie kul
    dir.scale(1.0 / d)

    corr = (b1.radius + b2.radius - d) / 2.0
    b1.pos.add(dir, -corr)
    b2.pos.add(dir, corr)

    v1 = b1.vel.dot(dir)
    v2 = b2.vel.dot(dir)

    m1 = b1.mass
    m2 = b2.mass
    #Parametr zderzenia
    r = scene.restitution
    #Wynik kolizji
    newV1 = (m1*v1 + m2*v2 - m2*(v1 - v2)*r) / (m1 + m2)
    newV2 = (m1*v1 + m2*v2 - m1*(v2 - v1)*r) / (m1 + m2)

    b1.vel.add(dir, newV1 - v1)
    b2.vel.add(dir, newV2 - v2)

def handle_wall_collision(ball):
    w = scene.worldSize
    #lewa i prawa granica ekranu
    if ball.pos.x < ball.radius:
        ball.pos.x = ball.radius
        ball.vel.x *= -1

    if ball.pos.x > w.x - ball.radius:
        ball.pos.x = w.x - ball.radius
        ball.vel.x *= -1
    #górna i dolna granca ekranu
    if ball.pos.y < ball.radius:
        ball.pos.y = ball.radius
        ball.vel.y *= -1

    if ball.pos.y > w.y - ball.radius:
        ball.pos.y = w.y - ball.radius
        ball.vel.y *= -1

#%% DRAWING

def draw():
    win.fill((30, 30, 30))
    for b in scene.balls:
        pygame.draw.circle(
            win,
            (255, 0, 0),
            (cX(b.pos.x), cY(b.pos.y)),
            int(b.radius * cScale)
        )
    pygame.display.flip()



#MAIN LOOP
clock = pygame.time.Clock()
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





