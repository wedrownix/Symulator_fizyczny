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
    return pos.y *cSale



def draw():
    pass

def simulate():
    pass

def update():
    simulate();
    draw();

    pass

update()