import pygame
pygame.init()

#TWORZENIE OKNA, nasz win
screen_width = 480
screen_height = 500
win = pygame.display.set_mode((screen_width,screen_height))

pygame.display.set_caption("Nauka_Pygame")


"""##STARA OPCJA
walkRight = [pygame.image.load('Game_images_test/R1.png'), pygame.image.load('Game_images_test/R2.png'), pygame.image.load('Game_images_test/R3.png'), pygame.image.load('Game_images_test/R4.png'), pygame.image.load('Game_images_test/R5.png'), pygame.image.load('Game_images_test/R6.png'), pygame.image.load('Game_images_test/R7.png'), pygame.image.load('Game_images_test/R8.png'), pygame.image.load('Game_images_test/R9.png')]
walkLeft = [pygame.image.load('Game_images_test/L1.png'), pygame.image.load('Game_images_test/L2.png'), pygame.image.load('Game_images_test/L3.png'), pygame.image.load('Game_images_test/L4.png'), pygame.image.load('Game_images_test/L5.png'), pygame.image.load('Game_images_test/L6.png'), pygame.image.load('Game_images_test/L7.png'), pygame.image.load('Game_images_test/L8.png'), pygame.image.load('Game_images_test/L9.png')]
bg = pygame.image.load('Game_images_test/bg.jpg')
char = pygame.image.load('Game_images_test/standing.png')"""
# WCZYTYWANIE GRAFIKI
from pathlib import Path
# 1. Ustalamy bezpieczną ścieżkę do folderu z grafikami
# Kod szuka folderu "Game_images_test" tam, gdzie leży ten skrypt .py
IMG_DIR = Path(__file__).parent / "Game_images_test"

walkRight = [pygame.image.load(str(IMG_DIR / f"R{i}.png")) for i in range(1, 10)]
walkLeft  = [pygame.image.load(str(IMG_DIR / f"L{i}.png")) for i in range(1, 10)]
bg   = pygame.image.load(str(IMG_DIR / "bg.jpg"))
char = pygame.image.load(str(IMG_DIR / "standing.png"))

clock = pygame.time.Clock()
#PARAMETRY PIERWSZEJ POSTACI
x = 50
y = 400
width = 64
height = 64
vel = 5
isJump = False
jumpCount = 10
left = False
right = False
walkCount = 0

#Tworzę funkcję po to by cały czas nie rysować w main loop
def redrawGameWindow():
    global walkCount
    win.blit(bg, (0,0))

    if walkCount +1 >= 27: #kązdy rysunek na 3 klatki. mam 9 rysunków czyli 27
        walkCount = 0

    if left:
        win.blit(walkLeft[walkCount//3], (x,y)) #Dzielenie całkowite czyli 5//3 =1, spowalniam animację, co 3 klatki gry, jedna klatka animacji
        walkCount += 1
    elif right:
        win.blit(walkRight[walkCount//3], (x,y))
        walkCount += 1
    else:
        win.blit(char, (x, y))
    pygame.display.update()

#MAIN LOOP
run = True
while run:
    clock.tick(27)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    keys = pygame.key.get_pressed()
#Z uwagi na to, że lewy górny róg ekranu to 00,
    # a prawy dolny to 500,500 należy odpowiednio skonfigurować komendy ruchu
    #teraz stworzyłem blokadę zabraniającą przenikać przez ściany
    if keys[pygame.K_LEFT] and x> vel:
        x -= vel
        left = True
        right = False
    elif keys[pygame.K_RIGHT] and x< screen_width - width -vel:
        x += vel
        right = True
        left = False
    else:
        left = False
        right = False
        walkCount = 0
    if not(isJump): #Podczas skoku nie można pozwolić użytkownikowi by poruszał się w górę lub dół
        # BLOKUJĘ MOŻLIWOŚĆ PORUSZANIA SIĘ W GÓRĘ I W DÓŁ
        # if keys[pygame.K_UP] and y > vel:
        #     y -= vel
        # if keys[pygame.K_DOWN] and y < screen_height - height -vel:
        #     y += vel
        if keys[pygame.K_SPACE]:
            isJump = True
            right = False
            left = False
            walkCount = 0
    else:
        #Na początek szybko przyśpieszam do góry, ale coraz wolniej
        #10^2, 9^2 itd. potem gdy dojedę do 0 to zaczynam przyśpieszać w dół
        #-1^2 -2^2 itd.
        if jumpCount >= -10:
            neg = 1
            if jumpCount < 0:
                neg = -1
            y -= (jumpCount ** 2) * 0.5 * neg
            jumpCount -= 1
        else:
            isJump = False
            jumpCount = 10

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
    redrawGameWindow()

pygame.quit()


