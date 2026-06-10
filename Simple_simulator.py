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



class Ball:
    def __init__(self, radius, x, y):
        self.radius = radius
        self.x = x
        self.y = y
        #self.vx = vx
        #self.vy = vy

ball = Ball(x = 5, y = 5, radius = 5)

#MAIN LOOP
run = True
while run:
    pygame.time.delay(100)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
    #DODAWANIE prostokąta - kolory są RGB
    pygame.draw.circle(win, (255,0,0), (cX(ball.x), cY(ball.y)), ball.radius*cScale)
    pygame.display.update()
pygame.quit()





