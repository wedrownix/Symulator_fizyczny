import pygame
pygame.init()

#TWORZENIE OKNA, nasz win
screen_width = 500
screen_height = 480
win = pygame.display.set_mode((screen_width,screen_height))
pygame.display.set_caption("Nauka_Pygame")



# WCZYTYWANIE GRAFIKI
from pathlib import Path
IMG_DIR = Path(__file__).parent / "Game_images_test"
walkRight = [pygame.image.load(str(IMG_DIR / f"R{i}.png")) for i in range(1, 10)]
walkLeft  = [pygame.image.load(str(IMG_DIR / f"L{i}.png")) for i in range(1, 10)]
bg   = pygame.image.load(str(IMG_DIR / "bg.jpg"))
char = pygame.image.load(str(IMG_DIR / "standing.png"))
clock = pygame.time.Clock()

class player(object):
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
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


def redrawGameWindow():
    global walkCount
    win.blit(bg, (0,0))

    if walkCount +1 >= 27:
        walkCount = 0
    if left:
        win.blit(walkLeft[walkCount//3], (x,y))
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
    if not(isJump):
        if keys[pygame.K_SPACE]:
            isJump = True
            right = False
            left = False
            walkCount = 0
    else:
        if jumpCount >= -10:
            neg = 1
            if jumpCount < 0:
                neg = -1
            y -= (jumpCount ** 2) * 0.5 * neg
            jumpCount -= 1
        else:
            isJump = False
            jumpCount = 10
    redrawGameWindow()
pygame.quit()


