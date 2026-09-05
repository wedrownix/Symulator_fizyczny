import math
import random
import pygame
pygame.init()
from typing import List

#%%TWORZENIE OKNA,
screen_width = 1500
screen_height = 1200
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Pinball")
clock = pygame.time.Clock()

score_font = pygame.font.SysFont(None, 48)

FLIPPER_HEIGHT = 1.7
cScale = min(screen_width,screen_height)/FLIPPER_HEIGHT
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

#%%OBJECTS
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
        self.pushVel = pushVel  # Wzmocnienie prędkości przy odbijaniu

class Flipper:
    def __init__(self,
                 radius,
                 pos,
                 length,
                 restAngle,
                 maxRotation,
                 angularVelocity,
                 restitution):

        # Stałe parametry
        self.radius = radius #promień fliperra
        self.pos = pos.clone() #punkt obrotu-zawias
        self.length = length
        self.restAngle = restAngle #kąt spoczynkowy
        self.maxRotation = abs(maxRotation) #maxroation
        self.sign = 1 if maxRotation >= 0 else -1 #znak odpowiadający za lewego i prawego flipera
        self.angularVelocity = angularVelocity #omega
        self.restitution = restitution #tłumienie
        # Parametry zmienne
        self.rotation = 0.0
        self.currentAngularVelocity = 0.0
        # -1 = flipper puszczony; dowolna wartość >= 0 = flipper wciśnięty.
        self.touchIdentifier = -1

    def simulate(self, dt):
        previousRotation = self.rotation
        pressed = self.touchIdentifier >= 0

        if pressed:
            self.rotation = min(
                self.rotation + dt * self.angularVelocity,
                self.maxRotation
            )
        else:
            self.rotation = max(
                self.rotation - dt * self.angularVelocity,
                0.0
            )

        self.currentAngularVelocity = (
            self.sign * (self.rotation - previousRotation) / dt
        )

    def select(self, pos): #Sprawdzenie, czy uzytkownik kliknął flipper, pos - pozycja myszk
        d = Vec2()
        d.subtractVectors(self.pos, pos) #Wektor od miejsca kliknięcia do zawiasu, jeśli kliknę w obszar okręgu wyznaczony przez ramię zawiasu to znaczy, że inicuję flipper
        return d.length() < self.length

    def getTip(self): #Tworzę wektor wzdłuż ramienia flipera o długości flippera
        angle = self.restAngle + self.sign * self.rotation

        direction = Vec2(
            math.cos(angle),
            math.sin(angle)
        )
        tip = self.pos.clone()
        tip.add(direction, self.length)
        return tip

#%%WORLD
class PhysicsScene:
    def __init__(self):
        self.gravity = Vec2(0.0, -3.0)
        self.dt = 1.0 / 60.0
        self.score = 0
        self.border = []
        self.balls = []
        self.obstacles = []
        self.flippers = []
scene = PhysicsScene()

def setup_scene():
    offset = 0.02
    scene.score = 0

    # Border - tworzę wielokąt z moimi granicami mapy

    scene.border = [
        Vec2(0.74, 0.25),
        Vec2(1.0 - offset, 0.40),
        Vec2(1.0 - offset, FLIPPER_HEIGHT - offset),
        Vec2(offset, FLIPPER_HEIGHT - offset),
        Vec2(offset, 0.40),
        Vec2(0.26, 0.25),
        Vec2(0.26, 0.00),
        Vec2(0.74, 0.00),
    ]

    # Balls

    radius = 0.08
    mass = math.pi * radius * radius

    scene.balls = [
        Ball(
            radius,
            mass,
            Vec2(0.92, 0.50),
            Vec2(-0.2, 3.5),
            restitution=0.2
        ),
        Ball(
            radius,
            mass,
            Vec2(0.08, 0.50),
            Vec2(0.2, 3.5),
            restitution=0.2
        )
    ]

    # Obstacles

    scene.obstacles = [
        Obstacle(0.10, Vec2(0.25, 0.60), 2.0),
        Obstacle(0.10, Vec2(0.75, 0.50), 2.0),
        Obstacle(0.12, Vec2(0.70, 1.00), 2.0),
        Obstacle(0.10, Vec2(0.20, 1.20), 2.0),
    ]

    # Flippers

    scene.flippers = []

    radius = 0.03
    length = 0.20
    maxRotation = 1.0
    restAngle = 0.5
    angularVelocity = 10.0
    restitution = 0.0
    pos1 = Vec2(0.26, 0.22)
    pos2 = Vec2(0.74, 0.22)
    scene.flippers = [
        Flipper(
            radius,
            pos1,
            length,
            -restAngle,
            maxRotation,
            angularVelocity,
            restitution
        ),
        Flipper(
            radius,
            pos2,
            length,
            math.pi + restAngle,
            -maxRotation,
            angularVelocity,
            restitution
        )
    ]
#%%Draw
def draw_disc(x, y, radius, color):
    pygame.draw.circle(
        win,
        color,
        (int(cX(x)), int(cY(y))),
        int(radius * cScale)
    )


def draw():
    win.fill((255, 255, 255))
    # ---------------- Border ----------------
    if len(scene.border) >= 2:
        points = []
        for v in scene.border:
            points.append((cX(v.x), cY(v.y)))
        pygame.draw.lines(
            win,
            (0, 0, 0),
            True,
            points,
            5
        )
    # ---------------- Balls ----------------
    for ball in scene.balls:
        draw_disc(
            ball.pos.x,
            ball.pos.y,
            ball.radius,
            (32, 32, 32)
        )
    # ---------------- Obstacles ----------------
    for obstacle in scene.obstacles:
        draw_disc(
            obstacle.pos.x,
            obstacle.pos.y,
            obstacle.radius,
            (255, 128, 0)
        )
    # ---------------- Flippers ----------------
    for flipper in scene.flippers:
        angle = flipper.restAngle + flipper.sign * flipper.rotation

        x1 = flipper.pos.x
        y1 = flipper.pos.y

        x2 = x1 + flipper.length * math.cos(angle)
        y2 = y1 + flipper.length * math.sin(angle)

        # prostokąt zastępujemy grubą linią
        pygame.draw.line(
            win,
            (255, 0, 0),
            (cX(x1), cY(y1)),
            (cX(x2), cY(y2)),
            int(2 * flipper.radius * cScale)
        )
        draw_disc(x1, y1, flipper.radius, (255, 0, 0))
        draw_disc(x2, y2, flipper.radius, (255, 0, 0))

    #rysuję ramkę
    score_surface = score_font.render(f"Wynik: {scene.score}", True, (0, 0, 0))
    win.blit(score_surface, (30, 30))

    pygame.display.flip()



#%%Collision handling
def handle_ball_ball_collision(b1: Ball, b2: Ball):
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


def handle_ball_obstacle_collision(ball: Ball, obstacle: Obstacle):
    #Badam różnicę między odległościami
    dir = Vec2().subtractVectors(ball.pos, obstacle.pos)
    d = dir.length()
    if d == 0 or d > ball.radius + obstacle.radius:
        return
    #Należy skorygować położenie kul
    dir.scale(1.0 / d)

    corr = ball.radius + obstacle.radius - d
    ball.pos.add(dir, corr)

    v = ball.vel.dot(dir)
    ball.vel.add(dir, obstacle.pushVel - v)

    return True


def handle_ball_flipper_collision(ball: Ball, flipper:Flipper):

    closest = closest_point_on_segment(ball.pos, flipper.pos, flipper.getTip() )
    dir = Vec2().subtractVectors(ball.pos, closest)
    d = dir.length()
    if d == 0 or d > ball.radius + flipper.radius:
        return
    dir.scale(1.0 / d)

    corr = ball.radius + flipper.radius - d
    ball.pos.add(dir, corr)

    #Teraz zajmę się zmianą prędkości
    radius = closest.clone()
    radius.add(dir, flipper.radius)
    radius.subtract(flipper.pos)
    surface_Vel = radius.perp()
    surface_Vel.scale(flipper.currentAngularVelocity)

    v = ball.vel.dot(dir)
    vnew = surface_Vel.dot(dir)

    ball.vel.add(dir, vnew - v)


def handle_ball_border_collision(ball: Ball, border: List[Vec2]):

    if len(border) <3:
        return

    closest = Vec2()
    ab = Vec2()
    normal = Vec2()
    min_dist = 0.0
#Border to zamknięty wielokąt - lista wierzchołków, gdzie ostatni
    # łączy się z pierwszym. Dla każdej krawędzi liczę najbliższy punkt
    # do środka kuli i wybieram globalnie najbliższą krawędź.
    for i in range(len(border)):
        a = border[i]
        b = border[(i + 1) % len(border)]
        c = closest_point_on_segment(ball.pos, a, b)
        d = Vec2().subtractVectors(ball.pos, c)
        dist = d.length()
        if i == 0 or dist < min_dist:
            min_dist = dist
            closest.set(c)
            ab.subtractVectors(b, a)
            normal = ab.perp()

    d = Vec2().subtractVectors(ball.pos, closest)
    dist = d.length()
    if dist == 0.0:
        d.set(normal)
        dist = normal.length()
    d.scale(1.0 / dist)

    if d.dot(normal) >= 0.0:
        if dist > ball.radius:
            return
        ball.pos.add(d, ball.radius - dist)
    else:
        ball.pos.add(d, -(dist + ball.radius))

    # Odbicie: składowa prędkości wzdłuż d zostaje "wyprostowana" tak,
    # by zawsze wskazywała na zewnątrz (abs), z tłumieniem restytucją.
    v = ball.vel.dot(d)
    v_new = abs(v) * ball.restitution
    ball.vel.add(d, v_new - v)

#%% Simulations

def simulate():
    for flipper in scene.flippers:
        flipper.simulate(scene.dt)
    for i, ball in enumerate(scene.balls):
        ball.simulate(scene.gravity, scene.dt)

        for other in scene.balls[i + 1:]:
            handle_ball_ball_collision(ball, other)

        for obstacle in scene.obstacles:
            if handle_ball_obstacle_collision(ball, obstacle):
                scene.score += 1

        for flipper in scene.flippers:
            handle_ball_flipper_collision(ball, flipper)

        handle_ball_border_collision(ball, scene.border)

#%%MAIN LOOP

setup_scene()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    scene.flippers[0].touchIdentifier = 0 if keys[pygame.K_LEFT] else -1  # jeśli wciśnięty klawisz to zaczyna flipper przyśpieszać
    scene.flippers[1].touchIdentifier = 0 if keys[pygame.K_RIGHT] else -1

    simulate()
    draw()
    clock.tick(60)

pygame.quit()
