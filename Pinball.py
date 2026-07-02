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

