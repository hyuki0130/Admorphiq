def _extract_at(pts, ptset, s, need):
    used=set(); frames=[]
    for (r,c) in pts:
        if (r,c) in used: continue
        sq=[(r,c),(r,c+s),(r+s,c),(r+s,c+s)]
        present=[p for p in sq if p in ptset and p not in used]
        if len(present)>=need and (r,c) in present:
            for p in present: used.add(p)
            rr=round(sum(p[0] for p in sq)/4); cc=round(sum(p[1] for p in sq)/4)
            frames.append((rr,cc))
    return frames, used

def extract_frames(corners):
    pts=sorted(set(corners))
    if len(pts)<3: return []
    ptset=set(pts)
    rows={}; cols={}
    for (r,c) in pts:
        rows.setdefault(r,[]).append(c); cols.setdefault(c,[]).append(r)
    hg={abs(a-b) for cs in rows.values() for a in cs for b in cs if a<b}
    vg={abs(a-b) for rs in cols.values() for a in rs for b in rs if a<b}
    cand=sorted(hg & vg) or sorted(hg|vg)
    best=[]; best_cov=-1
    for s in cand:
        # strict 4-corner disjoint squares first, then sweep leftovers for 3-corner
        f4,u4=_extract_at(pts,ptset,s,4)
        leftover=[p for p in pts if p not in u4]
        f3,u3=_extract_at(leftover,ptset-u4,s,3)
        frames=sorted(f4+f3); cov=len(u4)+len(u3)
        if cov>best_cov or (cov==best_cov and len(frames)<len(best)):
            best_cov=cov; best=frames
    return best

l6=[(35,31),(35,28),(32,31),(32,28),(29,34),(29,31),(29,28),(29,25),
    (26,34),(26,31),(26,28),(26,25)]
print("L6:", extract_frames(l6), "(expect 3)")
print("lone:", extract_frames([(10,10),(10,13),(13,10),(13,13)]))
print("two:", extract_frames([(10,10),(10,13),(13,10),(13,13),(40,40),(40,43),(43,40),(43,43)]))
print("occluded(3):", extract_frames([(10,10),(10,13),(13,10)]))
# L5-like coarse: side larger, well separated (2 frames side ~ ? use 8)
print("coarse two:", extract_frames([(10,10),(10,18),(18,10),(18,18),(40,40),(40,48),(48,40),(48,48)]))
