"""Assemble supplied sheets preserving their original RGBA pixels."""
import hashlib
import json
from pathlib import Path
from PIL import Image
import numpy as np
from collections import deque
ROOT = Path(__file__).resolve().parents[1]
SHEETS = [
 ('idle',1.65,[(0,490,[0,420,835,1240,1672]),(490,941,[0,580,1080,1672])]),
 ('interaction',2.65,[(0,400,[0,180,345,515,698,909,1074,1279,1448]),(400,755,[0,285,495,708,913,1153,1448]),(755,1086,[0,200,401,603,801,994,1236,1448])]),
 ('work',2.45,[(0,400,[0,207,423,648,843,1043,1259,1448]),(400,735,[0,211,414,617,819,998,1235,1448]),(735,1086,[0,274,500,720,940,1192,1448])]),
 ('movement',2.8,[(0,420,[0,232,429,645,843,1030,1260,1448]),(420,770,[0,219,413,610,832,1025,1225,1448]),(770,1086,[0,213,411,606,807,1018,1228,1448])]),
 ('emotion',2.35,[(0,415,[0,215,420,602,823,1032,1217,1448]),(415,770,[0,205,407,603,813,1016,1236,1448]),(770,1086,[0,207,387,607,831,997,1220,1448])]),
]
def split_row(im, top, bottom, edges):
 """Assign connected artwork before cropping; capes may cross column guides."""
 row=im.crop((0,top,im.width,bottom))
 rgba=np.asarray(row)
 unseen=rgba[:,:,3]>0
 height,width=unseen.shape
 components=[]
 for yy,xx in zip(*np.where(unseen.copy())):
  if not unseen[yy,xx]: continue
  pending=deque([(int(xx),int(yy))]); unseen[yy,xx]=False; pixels=[]
  while pending:
   x,y=pending.popleft(); pixels.append((x,y))
   for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
    if 0<=nx<width and 0<=ny<height and unseen[ny,nx]:
     unseen[ny,nx]=False; pending.append((nx,ny))
  points=np.array(pixels)
  lo=points.min(axis=0); hi=points.max(axis=0)+1
  components.append((len(points),points,(*lo,*hi)))
 major=sorted(components,key=lambda c:c[0],reverse=True)[:len(edges)-1]
 major.sort(key=lambda c:(c[2][0]+c[2][2])/2)
 if min(c[0] for c in major)<2000:
  return [row.crop((l,0,r,row.height)).crop(row.crop((l,0,r,row.height)).getbbox()) for l,r in zip(edges,edges[1:])]
 groups=[[] for _ in major]
 for component in components:
  n,points,(l,t,r,b)=component
  if any(component is m for m in major):
   index=next(i for i,m in enumerate(major) if component is m)
  else:
   # Decorative marks follow the closest character silhouette bounding box.
   def distance(m):
    ml,mt,mr,mb=m[2]
    return max(ml-r,l-mr,0)**2+max(mt-b,t-mb,0)**2
   index=min(range(len(major)),key=lambda i:distance(major[i]))
  groups[index].append(points)
 result=[]
 for group in groups:
  points=np.concatenate(group); lo=points.min(axis=0); hi=points.max(axis=0)+1
  crop=np.zeros((hi[1]-lo[1],hi[0]-lo[0],4),dtype=np.uint8)
  crop[points[:,1]-lo[1],points[:,0]-lo[0]]=rgba[points[:,1],points[:,0]]
  result.append(Image.fromarray(crop))
 return result

def face_bounds(crop):
 """Measure the largest skin region, excluding hands, props and decorations."""
 rgba=np.asarray(crop)
 r,g,b,a=[rgba[:,:,i].astype(int) for i in range(4)]
 mask=(a>128)&(r>185)&(g>105)&(g<225)&(b>65)&(b<195)&(r-g>20)&(g-b>15)
 components=[]
 height,width=mask.shape
 for yy,xx in zip(*np.where(mask.copy())):
  if not mask[yy,xx]: continue
  pending=deque([(int(xx),int(yy))]); mask[yy,xx]=False; points=[]
  while pending:
   x,y=pending.popleft(); points.append((x,y))
   for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
    if 0<=nx<width and 0<=ny<height and mask[ny,nx]:
     mask[ny,nx]=False; pending.append((nx,ny))
  components.append(points)
 points=np.asarray(max(components,key=len))
 lo=points.min(axis=0); hi=points.max(axis=0)+1
 return [int(lo[0]),int(lo[1]),int(hi[0]-lo[0]),int(hi[1]-lo[1])]

def main():
 sources=[(name,scale,rows,Image.open(ROOT/f'assets/source-art/{name}.png').convert('RGBA')) for name,scale,rows in SHEETS]
 atlas=Image.new('RGBA',(8*640,14*500))
 cells,provenance=[],[]
 offset=row_id=0
 for name,scale,rows,im in sources:
  if im.getchannel('A').getextrema() != (0,255): raise ValueError(name)

  provenance.append(dict(file=f'source-art/{name}.png',sha256=hashlib.sha256((ROOT/f'assets/source-art/{name}.png').read_bytes()).hexdigest()))
  for top,bottom,edges in rows:
   for col,crop in enumerate(split_row(im,top,bottom,edges)):
    w,h=crop.size
    if w>640 or h>500: raise ValueError((name,row_id,col,w,h))
    atlas.paste(crop,(col*640,row_id*500))
    face=face_bounds(crop)
    # Profile faces expose less skin than frontal faces; calibrate their
    # apparent width so turning does not enlarge the head and body.
    profile = .72 if (row_id==2 and col in (3,4,6)) or (row_id==8 and col<5) else 1.
    factor=240*profile/face[2]
    x=384-(face[0]+face[2]/2)*factor
    x=max(24,min(x,744-w*factor))
    cells.append(dict(row=row_id,col=col,sheet=name,source=[col*640,row_id*500,w,h],face=face,profile=profile,target=[x,784-h*factor,w*factor,h*factor]))
   row_id+=1
  offset+=im.height
 path=ROOT/'assets/user-actions.png'
 atlas.save(path)
 manifest=dict(version=7,image=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),frame_size=[768,832],sources=provenance,frames=cells)
 (ROOT/'assets/user-actions.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
 bubbles=Image.open(ROOT/'assets/source-art/bubbles.png').convert('RGBA')
 rows=[(0,325,[0,466,807,1094,1448]),(325,600,[0,466,796,1097,1448]),(600,840,[0,300,590,874,1146,1448]),(840,1086,[0,205,376,554,732,910,1079,1250,1448])]
 names=['working','pink','waiting','success','thinking','thought-blue','thought-pink','alert','notice-blue','notice-yellow','green-angular','purple-cloud','burst-blue','heart','question','warning','ellipsis','sleep','confused','idea','sparkle']
 for name,(left,top,right,bottom) in zip(names,[(l,t,r,b) for t,b,edges in rows for l,r in zip(edges,edges[1:])]):
  crop=bubbles.crop((left,top,right,bottom))
  crop.crop(crop.getbbox()).save(ROOT/f'assets/bubble-{name}.png')
 print(f'Built {len(cells)} poses and {len(names)} bubbles from original alpha')
if __name__=='__main__': main()

