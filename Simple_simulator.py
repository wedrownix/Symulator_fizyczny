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


gravity = {"x":0, "y":-10}
timeStep = 1/60

class Ball:
    def __init__(self, radius, x, y, vx, vy):
        self.radius = radius
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

ball = Ball(radius = 0.2, x = 0.2, y = 0.2, vx = 10, vy =15 )

def simulate():
    ball.vx += gravity["x"] * timeStep
    ball.vy += gravity["y"] * timeStep
    ball.x += ball.vx * timeStep
    ball.y += ball.vy * timeStep

    if ball.x < 0:
        ball.x = 0
        ball.vx = -ball.vx

    if ball.x > simWidth:
        ball.x = simWidth
        ball.vx = -ball.vx

    if ball.y < 0:
        ball.y = 0
        ball.vy = -ball.vy


"""#MAIN LOOP
run = True
while run:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
    #DODAWANIE prostokąta - kolory są RGB
    pygame.draw.circle(win, (255,0,0), (cX(ball.x), cY(ball.y)), ball.radius*cScale)
    pygame.display.update()
pygame.quit()"""





