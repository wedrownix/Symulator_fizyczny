import math
import random
import pygame
pygame.init()


#%%TWORZENIE OKNA,
screen_width = 1000
screen_height = 700
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Pinball")
clock = pygame.time.Clock()


simMinWidth = 20 #definiuje minimalną odległość obserwowaną na ekranie
cScale = min(screen_width,screen_height)/simMinWidth
simWidth = screen_width/cScale
simHeight = screen_height/cScale

def cX(x):
    return x *cScale
def cY(y):
    return screen_height - y *cScale

#%% VECTOR
import math


class Vec2:
    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y

    def set(self, v):
        self.x = v.x
        self.y = v.y

    def clone(self):
        return Vec2(self.x, self.y)

    def add(self, v, s: float = 1.0):
        self.x += v.x * s
        self.y += v.y * s
        return self

    def addVectors(self, a, b):
        self.x = a.x + b.x
        self.y = a.y + b.y
        return self

    def subtract(self, v, s: float = 1.0):
        self.x -= v.x * s
        self.y -= v.y * s
        return self

    def subtractVectors(self, a, b):
        self.x = a.x - b.x
        self.y = a.y - b.y
        return self

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y)

    def scale(self, s: float):
        self.x *= s
        self.y *= s
        return self

    def dot(self, v):
        return self.x * v.x + self.y * v.y

    def perp(self):
        """Zwraca wektor prostopadły (-y, x)."""
        return Vec2(-self.y, self.x)

def closest_point_on_segment(p: Vec2, a: Vec2, b: Vec2) -> Vec2:
    ab = Vec2()
    ab.subtractVectors(b, a)

    t = ab.dot(ab)

    if t == 0.0:
        return a.clone()

    t = max(0.0, min(1.0, (p.dot(ab) - a.dot(ab)) / t))

    closest = a.clone()
    closest.add(ab, t)

    return closest

#%%OBJECT - BALL
class Ball:
    def __init__(self, radius, mass, pos, vel, restitution):
        self.radius = radius
        self.mass = mass
        self.restitution = restitution

        self.pos = pos.clone()
        self.vel = vel.clone()

    def simulate(self, gravity, dt):
        self.vel.add(gravity, dt)
        self.pos.add(self.vel, dt)

class Obstacle:
    def __init__(self, radius, pos, pushVel):
        self.radius = radius
        self.pos = pos.clone()
        self.pushVel = pushVel