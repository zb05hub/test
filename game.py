from collections import defaultdict
from functools import lru_cache
from typing import NamedTuple

K, M = 1, 2
POINTS = sorted({(x,y) for x in range(5) for y in range(2,7)} |
                {(x,y) for y in (0,8) for x in (0,2,4)} |
                {(x,y) for y in (1,7) for x in (1,2,3)}, key=lambda p:p[::-1])
IDS = {p:i for i,p in enumerate(POINTS)}
lines = [[(x,y) for x in range(5)] for y in range(2,7)]
lines += [[(x,y) for y in range(2,7)] for x in range(5)]
lines += [[(i,2+i) for i in range(5)],[(4-i,2+i) for i in range(5)]]
lines += [[a,b,c] for a,b,c in [
 ((0,4),(1,3),(2,2)),((2,2),(3,3),(4,4)),((0,4),(1,5),(2,6)),((2,6),(3,5),(4,4)),
 ((0,0),(2,0),(4,0)),((1,1),(2,1),(3,1)),((2,0),(2,1),(2,2)),
 ((0,0),(1,1),(2,2)),((4,0),(3,1),(2,2)),
 ((0,8),(2,8),(4,8)),((1,7),(2,7),(3,7)),((2,8),(2,7),(2,6)),
 ((0,8),(1,7),(2,6)),((4,8),(3,7),(2,6))]]
# 将相邻交点组成无向边。
EDGES = sorted({tuple(sorted((IDS[a],IDS[b]))) for l in lines for a,b in zip(l,l[1:])})
neighbors = defaultdict(list)
for a,b in EDGES:
    neighbors[a].append(b)
    neighbors[b].append(a)
# 预计算横向和纵向的单次跳吃路线。
jumps = defaultdict(list)
for a,(ax,ay) in enumerate(POINTS):
    for b in neighbors[a]:
        bx,by = POINTS[b]
        for c in neighbors[b]:
            cx,cy = POINTS[c]
            dx,dy = bx-ax,by-ay
            ex,ey = cx-bx,cy-by
            if (dx == ex == 0 and dy*ey > 0) or (dy == ey == 0 and dx*ex > 0):
                jumps[a].append((b,c))

class State(NamedTuple):
    board: tuple
    side: int = K
    reserve: int = 16
    captured: int = 0

# 按图示摆放两位国王和八枚大臣。
def initial():
    b = [0]*len(POINTS)
    for p in [(2,2),(2,6)]: b[IDS[p]] = K
    for y in (3,4,5):
        for x in (1,2,3):
            if (x,y)!=(2,4): b[IDS[x,y]] = M
    return State(tuple(b))

# 按连线和当前阶段生成合法着法。
def moves(s):
    b,side,reserve,_ = s
    if side == M and reserve:
        return [(-1,i,-1) for i,v in enumerate(b) if not v]
    result = []
    for i,v in enumerate(b):
        if v != side: continue
        if side == K:
            result.extend((i,c,j) for j,c in jumps[i] if b[j]==M and not b[c])
        result.extend((i,j,-1) for j in neighbors[i] if not b[j])
    return result

# 执行一次着法后立即换方。
def play(s,m):
    a,b,c = m
    board = list(s.board)
    if a>=0: board[a]=0
    board[b]=s.side
    if c>=0: board[c]=0
    return State(tuple(board),3-s.side,s.reserve-(a<0),s.captured+(c>=0))

# 按吃子数和合法着法判定胜负。
def winner(s, legal):
    if s.captured >= 11: return K
    if not legal: return 3-s.side
    return 0

# 搜索并选择当前一方的最佳着法。
def choose(s):
    # 按吃子数和国王行动空间评价局面。
    @lru_cache(maxsize=24000)
    def evaluate(t):
        km = moves(t._replace(side=K))
        return 85*t.captured + 4*len(km) + 12*sum(c>=0 for _,_,c in km) - 2*(16-t.reserve)
    # 递归搜索并剪去不影响结果的分支。
    def search(t,depth,lo,hi):
        legal = moves(t)
        w = winner(t,legal)
        if w: return (10000+depth)*(1 if w==K else -1)
        if not depth: return evaluate(t)
        sign = 1 if t.side==K else -1
        score = -float('inf') if sign==1 else float('inf')
        for child in sorted((play(t,m) for m in legal),key=evaluate,reverse=sign==1):
            value = search(child,depth-1,lo,hi)
            if sign==1: score=max(score,value); lo=max(lo,score)
            else: score=min(score,value); hi=min(hi,score)
            if lo>=hi: break
        return score
    legal = moves(s)
    if winner(s,legal): return None
    sign = 1 if s.side==K else -1
    ordered = sorted(legal,key=lambda m:sign*evaluate(play(s,m)),reverse=True)
    best,score = ordered[0],-float('inf')
    for m in ordered:
        lo,hi = (score,float('inf')) if sign==1 else (-float('inf'),-score)
        v=sign*search(play(s,m),3,lo,hi)
        if v>score: best,score=m,v
    return best
