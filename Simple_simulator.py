import pygame
pygame.init()
import numpy as np

#TWORZENIE OKNA,
screen_width = 500
screen_height = 480
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Nauka_Symulatora")


simMinWidth = 20 #definiuje minimalną odległość obserwowaną na ekranie
cSale = min(screen_width,screen_height)/simMinWidth
simWidth = screen_width/cSale
simHeight = screen_height/cSale

def cX(pos):
    return pos.x *cSale
def cY(pos):
    return screen_height - pos.y *cSale



class Ball:
    def __init__(self, radius, x, y, vx, vy):
        self.radius = radius
        self.x = x
        self.y = y
        #self.vx = vx
        #self.vy = vy

ball = Ball(x = 0.2, y = 0.2, r = 0.2)

"""#MAIN LOOP
run = True
while run:
    pygame.time.delay(100)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False
    #DODAWANIE prostokąta - kolory są RGB
    pygame.draw.circle(win, (255,0,0), (ball.x, ball.y), ball.r)
    pygame.display.update()
pygame.quit()

"""



