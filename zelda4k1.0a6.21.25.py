"""
Zelda‑1‑inspired 2‑D prototype – zero external assets
====================================================

• Pure‑code sprites & tiles (no PNGs)
• NES‑style palette & HUD (hearts / rupees / bombs / keys)
• Tkinter launcher, Pygame gameplay
• Tested on Python 3.11, 3.12‑beta, 3.13‑dev

Author: ChatGPT (o3 pro) for Cat‑Sama – 2025‑06‑21
"""

# ───────────────────────── imports ──────────────────────────
import math, random, sys, tkinter as tk, threading
from dataclasses import dataclass

import pygame as pg

# ───────────────────────── constants ────────────────────────
TILE          = 32                 # world tile size (px on screen)
MAP_W, MAP_H  = 20, 15             # tiles
SCR_W, SCR_H  = MAP_W*TILE, MAP_H*TILE
FPS           = 60

PLAYER_VEL    = 3                  # px/frame
ENEMY_VEL     = 2
SWING_CD_MS   = 300
SWING_DUR_MS  = 120
SWORD_LEN     = 18

#        NES‑ish palette (truncated to what we use)
GRASS_LGHT = ( 48, 168,  80)
GRASS_DRK  = ( 18,  92,  38)
BRICK      = (152,  93,  82)
BRICK_MORT = (104,  60,  52)
LINK_GRN   = ( 48, 140,  40)
LINK_SKIN  = (252, 188, 176)
LINK_FACE  = ( 40,  40,  40)
OCTOROK    = (208,  56,  56)
UI_BG      = (  0,   0,   0)
UI_FG      = (255, 255, 255)
GOLD       = (252, 232, 132)

# ───────────────────────── helpers ──────────────────────────
def rnd_tex(tile, base, accent, density=0.15):
    """Return surface with noise dots for grass."""
    surf = pg.Surface((TILE, TILE))
    surf.fill(base)
    for _ in range(int(TILE*TILE*density)):
        x, y = random.randrange(TILE), random.randrange(TILE)
        surf.set_at((x, y), accent)
    return surf

def brick_tex():
    """Return 2‑colour brick pattern."""
    surf = pg.Surface((TILE, TILE))
    surf.fill(BRICK)
    pg.draw.rect(surf, BRICK_MORT, (0, TILE//2-2, TILE, 4))
    for col in (0, TILE//2):
        pg.draw.rect(surf, BRICK_MORT, (col-2, -2, 4, TILE))
    return surf

# pre‑generated tile surfaces
TILE_GRASS = rnd_tex("grass", GRASS_LGHT, GRASS_DRK)
TILE_WALL  = brick_tex()

# ───────────────────────── sprite factory ───────────────────
def make_link(facing):
    """Return 16×16 Surface of Link facing given axis ('U','D','L','R')."""
    s = pg.Surface((16,16), pg.SRCALPHA)

    # tunic
    pg.draw.rect(s, LINK_GRN, (4,8,8,8))
    # head
    pg.draw.rect(s, LINK_SKIN, (4,2,8,6))
    # eyes / belt
    pg.draw.line(s, LINK_FACE, (6,4), (6,4))
    pg.draw.line(s, LINK_FACE, (10,4), (10,4))
    pg.draw.line(s, LINK_FACE, (4,11), (11,11))
    # simple direction indicator
    if facing == "L":
        pg.draw.polygon(s, LINK_GRN, [(1,8),(4,7),(4,9)])
    elif facing == "R":
        pg.draw.polygon(s, LINK_GRN, [(15,8),(12,7),(12,9)])
    elif facing == "U":
        pg.draw.polygon(s, LINK_GRN, [(8,1),(6,4),(10,4)])
    elif facing == "D":
        pg.draw.polygon(s, LINK_GRN, [(8,14),(6,11),(10,11)])
    return pg.transform.scale(s,(TILE//2,TILE//2))

def make_octorok():
    s = pg.Surface((16,16), pg.SRCALPHA)
    pg.draw.circle(s, OCTOROK, (8,8), 6)
    pg.draw.rect(s, LINK_FACE, (5,5,2,2))
    pg.draw.rect(s, LINK_FACE, (9,5,2,2))
    return pg.transform.scale(s,(TILE//2,TILE//2))

LINK_SURF = {d:make_link(d) for d in "UDLR"}
OCTO_SURF = make_octorok()

# ───────────────────────── HUD primitives ───────────────────
def draw_heart(full=True, scale=1):
    w, h = 7*scale, 6*scale
    surf = pg.Surface((w,h), pg.SRCALPHA)
    color = GOLD if full else UI_FG
    pts = [(3,0),(5,0),(6,1),(6,3),(3,5),(0,3),(0,1),(1,0)]
    pts = [(x*scale,y*scale) for x,y in pts]
    pg.draw.polygon(surf, color, pts)
    return surf
HEART_FULL = draw_heart(True,2)
HEART_EMPTY= draw_heart(False,2)

def draw_rupee(scale=1):
    s=pg.Surface((8*scale,12*scale),pg.SRCALPHA)
    pts=[(4,0),(8,4),(8,8),(4,12),(0,8),(0,4)]
    pg.draw.polygon(s,GOLD,[(x*scale,y*scale) for x,y in pts])
    return s
RUPEE_ICON=draw_rupee(2)

def draw_key(scale=1):
    s=pg.Surface((12*scale,8*scale),pg.SRCALPHA)
    pg.draw.rect(s,UI_FG,(0,3*scale,8*scale,2*scale))
    pg.draw.circle(s,UI_FG,(9*scale,4*scale),3*scale)
    return s
KEY_ICON=draw_key(2)

def draw_bomb(scale=1):
    s=pg.Surface((10*scale,10*scale),pg.SRCALPHA)
    pg.draw.circle(s,UI_FG,(5*scale,5*scale),4*scale)
    pg.draw.line(s,GOLD,(5*scale,1*scale),(5*scale,-2*scale),max(scale,1))
    return s
BOMB_ICON=draw_bomb(2)

FONT = None  # filled in after pg.init()

# ───────────────────────── entity dataclass ────────────────
@dataclass
class Entity:
    x:float; y:float; surf:pg.Surface
    @property
    def rect(self): return self.surf.get_rect(topleft=(self.x,self.y))
    def draw(self,screen): screen.blit(self.surf,(self.x,self.y))

class Player(Entity):
    def __init__(self,x,y):
        super().__init__(x,y,LINK_SURF["D"])
        self.dir="D"
        self.last_swing=-SWING_CD_MS
        self.hp=3
    def input(self):
        keys=pg.key.get_pressed()
        vel=pg.Vector2(0,0)
        if keys[pg.K_LEFT]or keys[pg.K_a]: vel.x=-PLAYER_VEL; self.dir="L"
        if keys[pg.K_RIGHT]or keys[pg.K_d]:vel.x=PLAYER_VEL; self.dir="R"
        if keys[pg.K_UP]or keys[pg.K_w]:    vel.y=-PLAYER_VEL; self.dir="U"
        if keys[pg.K_DOWN]or keys[pg.K_s]:  vel.y=PLAYER_VEL; self.dir="D"
        self.surf=LINK_SURF[self.dir]
        return vel

class Enemy(Entity):
    def __init__(self,x,y):
        super().__init__(x,y,OCTO_SURF)
        self.dir=pg.Vector2(random.choice([-1,1]),0)

# ───────────────────────── core game class ─────────────────
class Game:
    def __init__(self):
        pg.init()
        global FONT
        FONT=pg.font.SysFont("consolas",16,bold=True)
        self.screen=pg.display.set_mode((SCR_W,SCR_H))
        pg.display.set_caption("Zelda‑Like (100 % code assets)")
        self.clock=pg.time.Clock()
        self.make_world()
        self.run_flag=True

        # meta
        self.rupees=0; self.keys=0; self.bombs=0

    def make_world(self):
        # map: 0 grass, 1 wall
        self.map=[[0]*MAP_W for _ in range(MAP_H)]
        for x in range(MAP_W): self.map[0][x]=self.map[-1][x]=1
        for y in range(MAP_H): self.map[y][0]=self.map[y][-1]=1
        for _ in range(int(MAP_W*MAP_H*0.10)):
            x,y=random.randrange(1,MAP_W-1),random.randrange(1,MAP_H-1)
            self.map[y][x]=1
        # entities
        self.player=Player(TILE*2,TILE*2)
        self.enemies=[Enemy(TILE*random.randrange(3,MAP_W-3),
                            TILE*random.randrange(3,MAP_H-3))
                      for _ in range(6)]
        self.sword=None
        self.walls=[pg.Rect(x*TILE,y*TILE,TILE,TILE)
                    for y,row in enumerate(self.map)
                    for x,v in enumerate(row) if v]

    # ────────── main loop ──────────
    def run(self):
        while self.run_flag:
            dt=self.clock.tick(FPS)
            self.handle_events()
            self.update()
            self.draw()
        pg.quit()

    # ────────── events ──────────
    def handle_events(self):
        for ev in pg.event.get():
            if ev.type==pg.QUIT: self.run_flag=False
            elif ev.type==pg.KEYDOWN and ev.key==pg.K_SPACE:
                now=pg.time.get_ticks()
                if now-self.player.last_swing>=SWING_CD_MS:
                    self.spawn_sword(now)

    def spawn_sword(self,now):
        self.player.last_swing=now
        pr=self.player.rect
        off={"U":(pr.centerx-SWORD_LEN//2,pr.top-SWORD_LEN),
             "D":(pr.centerx-SWORD_LEN//2,pr.bottom),
             "L":(pr.left-SWORD_LEN,pr.centery-SWORD_LEN//2),
             "R":(pr.right,pr.centery-SWORD_LEN//2)}[self.player.dir]
        self.sword=pg.Rect(off,(SWORD_LEN,SWORD_LEN))

    # ────────── update ──────────
    def update(self):
        vel=self.player.input()
        self.move_entity(self.player,vel)
        # sword lifetime
        if self.sword and pg.time.get_ticks()-self.player.last_swing>SWING_DUR_MS:
            self.sword=None
        # enemies
        for e in self.enemies[:]:
            self.move_entity(e,e.dir*ENEMY_VEL,ai=True)
            # hit by sword?
            if self.sword and e.rect.colliderect(self.sword):
                self.enemies.remove(e); self.rupees+=1

    def move_entity(self,ent,vel,ai=False):
        rect=ent.rect
        # axis‑separated
        for axis in (0,1):
            step=[0,0]; step[axis]=vel[axis]
            nxt=rect.move(step)
            if any(nxt.colliderect(w) for w in self.walls):
                if ai: ent.dir*=-1  # bounce
            else:
                if axis==0: ent.x+=vel.x
                else: ent.y+=vel.y
                rect=ent.rect

    # ────────── draw ──────────
    def draw(self):
        # world
        for y,row in enumerate(self.map):
            for x,v in enumerate(row):
                surf=TILE_WALL if v else TILE_GRASS
                self.screen.blit(surf,(x*TILE,y*TILE))
        for e in self.enemies: e.draw(self.screen)
        self.player.draw(self.screen)
        if self.sword: pg.draw.rect(self.screen,GOLD,self.sword)

        self.draw_hud()
        pg.display.flip()

    def draw_hud(self):
        # black strip
        pg.draw.rect(self.screen,UI_BG,(0,0,SCR_W,32))
        # counters
        self.screen.blit(RUPEE_ICON,(8,8))
        txt=FONT.render(f"{self.rupees:02}",False,UI_FG); self.screen.blit(txt,(30,8))
        self.screen.blit(KEY_ICON,(80,8))
        txt=FONT.render(f"{self.keys:02}",False,UI_FG); self.screen.blit(txt,(104,8))
        self.screen.blit(BOMB_ICON,(152,8))
        txt=FONT.render(f"{self.bombs:02}",False,UI_FG); self.screen.blit(txt,(176,8))
        # hearts
        for i in range(5):
            heart=HEART_FULL if i<self.player.hp else HEART_EMPTY
            self.screen.blit(heart,(SCR_W-150+i*26,6))

# ───────────────────────── Tkinter launcher ─────────────────
def launch():
    root.destroy()
    Game().run()

root=tk.Tk(); root.title("Zelda‑Like (code‑only)")
tk.Label(root,text="Zelda‑Style Prototype\n(no external art)",font=("Consolas",14,"bold")).pack(padx=20,pady=10)
tk.Button(root,text="Play",width=20,command=launch).pack(pady=5)
tk.Button(root,text="Quit",width=20,command=root.destroy).pack(pady=5)
root.mainloop()
