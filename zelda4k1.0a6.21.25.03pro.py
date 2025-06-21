"""
Zelda‑Like (pure‑code assets) – merged edition
=============================================

Combines:
  • “Zelda‑1‑inspired 2‑D prototype” (Tkinter + HUD + procedural tiles)
  • “tiny_zelda1.py” (ASCII map, minimal loop)

Author: ChatGPT (o3 pro) for Cat‑Sama – 2025‑06‑21
"""

# ───────────────────────── imports ──────────────────────────
import argparse, math, random, sys, tkinter as tk
from dataclasses import dataclass
import pygame as pg

# ───────────────────────── config ───────────────────────────
TILE        = 32
MAP_W, MAP_H= 20, 15           # used for random mode
FPS         = 60
PLAYER_VEL  = 3
ENEMY_VEL   = 2
SWING_CD_MS = 300
SWING_DUR_MS= 120
SWORD_LEN   = 18

MAP_MODE    = "ascii"   # "ascii" | "random"
SHOW_HUD    = True

PALETTE = dict(
    GRASS_L =( 48,168, 80), GRASS_D =(18, 92, 38),
    BRICK   =(152, 93, 82), BRICK_M =(104, 60, 52),
    LINK_G  =( 48,140, 40), LINK_S =(252,188,176), LINK_F =(40,40,40),
    OCTOROK =(208, 56, 56),
    UI_BG   =(0,0,0), UI_FG =(255,255,255), GOLD =(252,232,132),
    FLOOR   =( 97,161, 97), WALL   =( 27, 91, 27)
)

ASCII_MAP = [
"################",
"#......####....#",
"#......#..#....#",
"#..E...#..#....#",
"#......####....#",
"#..............#",
"#....L.........#",
"#..............#",
"################",
]

# ───────────────────────── helpers ──────────────────────────
def rnd_tex(base, accent, density=0.15):
    s = pg.Surface((TILE, TILE)); s.fill(base)
    for _ in range(int(TILE*TILE*density)):
        s.set_at((random.randrange(TILE), random.randrange(TILE)), accent)
    return s

def brick_tex():
    s = pg.Surface((TILE, TILE)); s.fill(PALETTE["BRICK"])
    pg.draw.rect(s, PALETTE["BRICK_M"], (0, TILE//2-2, TILE, 4))
    for col in (0, TILE//2):
        pg.draw.rect(s, PALETTE["BRICK_M"], (col-2, -2, 4, TILE))
    return s

TEX_GRASS = rnd_tex(PALETTE["GRASS_L"], PALETTE["GRASS_D"])
TEX_WALL  = brick_tex()

def make_link(facing):
    s = pg.Surface((16,16), pg.SRCALPHA)
    # tunic
    pg.draw.rect(s, PALETTE["LINK_G"], (4,8,8,8))
    # head
    pg.draw.rect(s, PALETTE["LINK_S"], (4,2,8,6))
    # eyes / belt
    pg.draw.line(s, PALETTE["LINK_F"], (6,4), (6,4))
    pg.draw.line(s, PALETTE["LINK_F"], (10,4), (10,4))
    pg.draw.line(s, PALETTE["LINK_F"], (4,11), (11,11))
    # dir cue
    if   facing=="L": pg.draw.polygon(s, PALETTE["LINK_G"], [(1,8),(4,7),(4,9)])
    elif facing=="R": pg.draw.polygon(s, PALETTE["LINK_G"], [(15,8),(12,7),(12,9)])
    elif facing=="U": pg.draw.polygon(s, PALETTE["LINK_G"], [(8,1),(6,4),(10,4)])
    elif facing=="D": pg.draw.polygon(s, PALETTE["LINK_G"], [(8,14),(6,11),(10,11)])
    return pg.transform.scale(s, (TILE//2, TILE//2))

def make_octorok():
    s = pg.Surface((16,16), pg.SRCALPHA)
    pg.draw.circle(s, PALETTE["OCTOROK"], (8,8), 6)
    pg.draw.rect(s, PALETTE["LINK_F"], (5,5,2,2))
    pg.draw.rect(s, PALETTE["LINK_F"], (9,5,2,2))
    return pg.transform.scale(s, (TILE//2, TILE//2))

LINK_SURF = {d: make_link(d) for d in "UDLR"}
OCTO_SURF = make_octorok()

# HUD icons
def _heart(full=True): pts=[(3,0),(5,0),(6,1),(6,3),(3,5),(0,3),(0,1),(1,0)]
def draw_poly(pts,col,scale=1):
    s=pg.Surface((8*scale,8*scale),pg.SRCALPHA)
    pg.draw.polygon(s,col,[(x*scale,y*scale) for x,y in pts]); return s
HEART_FULL  = draw_poly([(3,0),(5,0),(6,1),(6,3),(3,5),(0,3),(0,1),(1,0)], PALETTE["GOLD"],2)
HEART_EMPTY = draw_poly([(3,0),(5,0),(6,1),(6,3),(3,5),(0,3),(0,1),(1,0)], PALETTE["UI_FG"],2)
def _rupee(): return draw_poly([(4,0),(8,4),(8,8),(4,12),(0,8),(0,4)], PALETTE["GOLD"],2)
RUPEE_ICON=_rupee()
def _key(): s=pg.Surface((12,8),pg.SRCALPHA); pg.draw.rect(s,PALETTE["UI_FG"],(0,3,8,2)); pg.draw.circle(s,PALETTE["UI_FG"],(9,4),3); return pg.transform.scale(s,(24,16))
KEY_ICON=_key()
def _bomb(): s=pg.Surface((10,10),pg.SRCALPHA); pg.draw.circle(s,PALETTE["UI_FG"],(5,5),4); pg.draw.line(s,PALETTE["GOLD"],(5,1),(5,-2)); return pg.transform.scale(s,(20,20))
BOMB_ICON=_bomb()

# ───────────────────────── entity dataclass ────────────────
@dataclass
class Entity:
    x:float; y:float; surf:pg.Surface
    @property
    def rect(self): return self.surf.get_rect(topleft=(self.x,self.y))
    def draw(self,screen): screen.blit(self.surf,(self.x,self.y))

class Player(Entity):
    def __init__(self,x,y):
        super().__init__(x,y,LINK_SURF["D"]); self.dir="D"; self.last_swing=-SWING_CD_MS; self.hp=3
    def input(self):
        keys=pg.key.get_pressed(); vel=pg.Vector2(0,0)
        if keys[pg.K_LEFT] or keys[pg.K_a]:  vel.x=-PLAYER_VEL; self.dir="L"
        if keys[pg.K_RIGHT]or keys[pg.K_d]:  vel.x= PLAYER_VEL; self.dir="R"
        if keys[pg.K_UP]   or keys[pg.K_w]:  vel.y=-PLAYER_VEL; self.dir="U"
        if keys[pg.K_DOWN] or keys[pg.K_s]:  vel.y= PLAYER_VEL; self.dir="D"
        if vel.length_squared(): self.surf=LINK_SURF[self.dir]
        return vel

class Enemy(Entity):
    def __init__(self,x,y):
        super().__init__(x,y,OCTO_SURF); self.dir=pg.Vector2(random.choice([-1,1]),0)

# ───────────────────────── game class ───────────────────────
class Game:
    def __init__(self, ascii_map=None):
        pg.init(); self.font=pg.font.SysFont("consolas",16,bold=True)
        if ascii_map: self.cols=len(ascii_map[0]); self.rows=len(ascii_map)
        else:         self.cols,self.rows=MAP_W,MAP_H
        self.scr_w,self.scr_h=self.cols*TILE, self.rows*TILE
        self.screen=pg.display.set_mode((self.scr_w,self.scr_h))
        pg.display.set_caption("Zelda‑Like (merged)")
        self.clock=pg.time.Clock(); self.run_flag=True
        self.rupees=self.keys=self.bombs=0
        self.map=[]; self.walls=[]
        self.make_world(ascii_map)

    # world generation
    def make_world(self,ascii_map):
        if ascii_map:
            self.map=[[1 if ch=='#' else 0 for ch in row] for row in ascii_map]
            pcell,nexts=[],[]
            for r,row in enumerate(ascii_map):
                for c,ch in enumerate(row):
                    if ch=='L': pcell=(c,r)
                    elif ch=='E': nexts.append((c,r))
            self.player=Player(pcell[0]*TILE,pcell[1]*TILE)
            self.enemies=[Enemy(c*TILE,r*TILE) for c,r in nexts]
        else:
            self.map=[[0]*self.cols for _ in range(self.rows)]
            for x in range(self.cols): self.map[0][x]=self.map[-1][x]=1
            for y in range(self.rows): self.map[y][0]=self.map[y][-1]=1
            for _ in range(int(self.cols*self.rows*0.10)):
                x,y=random.randrange(1,self.cols-1),random.randrange(1,self.rows-1)
                self.map[y][x]=1
            self.player=Player(TILE*2,TILE*2)
            self.enemies=[Enemy(TILE*random.randrange(3,self.cols-3),
                                TILE*random.randrange(3,self.rows-3)) for _ in range(6)]
        self.sword=None
        self.walls=[pg.Rect(x*TILE,y*TILE,TILE,TILE)
                    for y,row in enumerate(self.map)
                    for x,v in enumerate(row) if v]

    # main loop
    def run(self):
        while self.run_flag:
            dt=self.clock.tick(FPS)
            self.handle_events(); self.update(); self.draw()
        pg.quit()

    # events
    def handle_events(self):
        for ev in pg.event.get():
            if ev.type==pg.QUIT: self.run_flag=False
            elif ev.type==pg.KEYDOWN and ev.key==pg.K_SPACE:
                now=pg.time.get_ticks()
                if now-self.player.last_swing>=SWING_CD_MS: self.spawn_sword(now)

    def spawn_sword(self,now):
        self.player.last_swing=now; pr=self.player.rect
        off={"U":(pr.centerx-SWORD_LEN//2,pr.top-SWORD_LEN),
             "D":(pr.centerx-SWORD_LEN//2,pr.bottom),
             "L":(pr.left-SWORD_LEN,pr.centery-SWORD_LEN//2),
             "R":(pr.right,pr.centery-SWORD_LEN//2)}[self.player.dir]
        self.sword=pg.Rect(off,(SWORD_LEN,SWORD_LEN))

    # update
    def update(self):
        vel=self.player.input(); self.move_entity(self.player,vel)
        if self.sword and pg.time.get_ticks()-self.player.last_swing>SWING_DUR_MS: self.sword=None
        for e in self.enemies[:]:
            self.move_entity(e,e.dir*ENEMY_VEL,ai=True)
            if self.sword and e.rect.colliderect(self.sword):
                self.enemies.remove(e); self.rupees+=1
            if e.rect.colliderect(self.player.rect):
                self.run_flag=False  # Game Over

    def move_entity(self,ent,vel,ai=False):
        rect=ent.rect
        for axis in (0,1):
            step=[0,0]; step[axis]=vel[axis]
            nxt=rect.move(step)
            if any(nxt.colliderect(w) for w in self.walls):
                if ai: ent.dir*=-1
            else:
                if axis==0: ent.x+=vel.x
                else: ent.y+=vel.y
                rect=ent.rect

    # draw
    def draw(self):
        for y,row in enumerate(self.map):
            for x,v in enumerate(row):
                s = TEX_WALL if v else (TEX_GRASS if MAP_MODE=="random" else None)
                if s: self.screen.blit(s,(x*TILE,y*TILE))
                elif MAP_MODE=="ascii":  # flat colour fill
                    col = PALETTE["WALL"] if v else PALETTE["FLOOR"]
                    pg.draw.rect(self.screen,col,(x*TILE,y*TILE,TILE,TILE))
        for e in self.enemies: e.draw(self.screen)
        self.player.draw(self.screen)
        if self.sword: pg.draw.rect(self.screen,PALETTE["GOLD"],self.sword)
        if SHOW_HUD: self.draw_hud()
        pg.display.flip()

    def draw_hud(self):
        pg.draw.rect(self.screen,PALETTE["UI_BG"],(0,0,self.scr_w,32))
        self.screen.blit(RUPEE_ICON,(8,8));  self.screen.blit(self.font.render(f"{self.rupees:02}",False,PALETTE["UI_FG"]),(30,8))
        self.screen.blit(KEY_ICON,(80,8));   self.screen.blit(self.font.render(f"{self.keys:02}",False,PALETTE["UI_FG"]),(104,8))
        self.screen.blit(BOMB_ICON,(152,8)); self.screen.blit(self.font.render(f"{self.bombs:02}",False,PALETTE["UI_FG"]),(176,8))
        for i in range(5):
            heart = HEART_FULL if i<self.player.hp else HEART_EMPTY
            self.screen.blit(heart,(self.scr_w-150+i*26,6))

# ───────────────────────── Tkinter launcher ─────────────────
def launch():
    root.destroy(); Game(ASCII_MAP if MAP_MODE=="ascii" else None).run()

# cli entry
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--headless",action="store_true",help="skip Tkinter launcher")
    ap.add_argument("--mode",choices=["ascii","random"],default=MAP_MODE)
    ap.add_argument("--nohud",action="store_true")
    args=ap.parse_args()
    MAP_MODE=args.mode; SHOW_HUD=not args.nohud
    if args.headless: Game(ASCII_MAP if MAP_MODE=="ascii" else None).run()
    else:
        root=tk.Tk(); root.title("Zelda‑Like (merged)")
        tk.Label(root,text="Zelda‑Like demo\n(code‑only assets)",font=("Consolas",14,"bold")).pack(padx=20,pady=10)
        tk.Button(root,text="Play",width=20,command=launch).pack(pady=5)
        tk.Button(root,text="Quit",width=20,command=root.destroy).pack(pady=5)
        root.mainloop()
