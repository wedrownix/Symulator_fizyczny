import pygame
pygame.init()

#TWORZENIE OKNA, nasz win
screen_width = 800
screen_height = 600
win = pygame.display.set_mode((screen_width,screen_height))

pygame.display.set_caption("Nauka_Pygame")
screen = pygame.display.set_mode((800,600))


#PARAMETRY PIERWSZEJ POSTACI
x = 50
y = 50
width = 40
height = 60
vel = 15

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
    #teraz stworzyłem blokadę zabraniającą przenikać przez ściany
    if keys[pygame.K_LEFT] and x> vel:
        x -= vel
    if keys[pygame.K_RIGHT] and x< screen_width - width -vel:
        x += vel
    if keys[pygame.K_UP] and y > vel:
        y -= vel
    if keys[pygame.K_DOWN] and y < screen_height - height -vel:
        y += vel
   #Pilnowanie granic ekranu - poprzez przechodzenie przez ekran
    # - wymyśliłem to samemu. teraz to komentuję, bo już nie jest ważne
    """
    if x >= screen_width:
        x -= screen_width
    if y >= screen_height:
        y -= screen_height
    if x < 0:
        x += screen_width
    if y < 0:
        y += screen_height"""

    win.fill((0,0,0))
    #DODAWANIE prostokąta - kolory są RGB, natomiast współrzędne x, y
    # to współrzędne lewego górnego rogu prostokąta
    pygame.draw.rect(win, (255,0,0), (x, y, width, height))
    pygame.display.update()
pygame.quit()


