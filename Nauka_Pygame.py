from tarfile import data_filter

import pygame
pygame.init()

#TWORZENIE OKNA, nasz win
win = pygame.display.set_mode((800,600))

pygame.display.set_caption("Nauka_Pygame")
screen = pygame.display.set_mode((800,600))


#PARAMETRY PIERWSZEJ POSTACI
x = 50
y = 50
width = 40
height = 60
vel = 5

#MAIN LOOP

run = True
while run:
    pygame.time.delay(100)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    keys = pygame.key.get_pressed()
#Z uwagi na to, że lewy górny róg ekranu to 00,
    # a prawy dolny to 500,500 należy odpowiednio skonfigurować komendy ruchu
    if keys[pygame.K_LEFT]:
        x -= vel
    if keys[pygame.K_RIGHT]:
        x += vel
    if keys[pygame.K_UP]:
        y -= vel
    if keys[pygame.K_DOWN]:
        y += vel

    #DODAWANIE prostokąta - kolory są RGB
    pygame.draw.rect(win, (255,0,0), (x, y, width, height))
    pygame.display.update()
pygame.quit()
