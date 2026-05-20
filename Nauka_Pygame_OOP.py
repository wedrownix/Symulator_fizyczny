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
        self.vel = 5
        self.isJump = False
        self.jumpCount = 10
        self.left = False
        self.right = False
        self.walkCount = 0

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

man = player(x=300, y=410, width=64, height=64)
run = True
while run:
    clock.tick(27)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT] and man.x> man.vel:
        man.x -= man.vel
        man.left = True
        man.right = False
    elif keys[pygame.K_RIGHT] and man.x< screen_width - man.width -man.vel:
        man.x += man.vel
        man.right = True
        man.left = False
    else:
        man.left = False
        man.right = False
        man.walkCount = 0
    if not(man.isJump):
        if keys[pygame.K_SPACE]:
            man.isJump = True
            man.right = False
            man.left = False
            man.walkCount = 0
    else:
        if man.jumpCount >= -10:
            neg = 1
            if man.jumpCount < 0:
                neg = -1
            man.y -= (man.jumpCount ** 2) * 0.5 * neg
            man.jumpCount -= 1
        else:
            man.isJump = False
            man.jumpCount = 10
    redrawGameWindow()
pygame.quit()


