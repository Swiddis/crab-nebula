import gbotlib
import math

# Note: Map is 470 by 360

def fill_circle(x, y, r, v, image):
    sx, sy, ex, ey = max(0, x-r), max(0, y-r), min(len(image[0]), x+r+1), min(len(image), y+r+1)
    for i in range(sy, ey):
        for j in range(sx, ex):
            if (i-y)**2 + (j-x)**2 <= r**2:
                image[i][j] += v

# It's possible we don't even need to fill the whole circle, just a cross with the appropriate radius may suffice
def fill_cross(x, y, r, v, image):
    sx, sy, ex, ey = max(0, x-r), max(0, y-r), min(len(image[0]), x+r+1), min(len(image), y+r+1)
    for ix in range(sx, ex):
        image[y][ix] += v
    for iy in range(sy, ey):
        if iy != y:
            image[x][iy] += v

# Or, no need to fill the cross at all
def fill_cross_points(x, y, r, v, image):
    if r == 0:
        image[y][x] += v
    else:
        sx, sy, ex, ey = max(0, x-r), max(0, y-r), min(len(image[0])-1, x+r), min(len(image)-1, y+r)
        image[sy][sx] += v
        image[sy][ex] += v
        image[ey][sx] += v
        image[ey][ex] += v

def build_image(galaxy):
    image = [[[0.0 for _a in range(94)] for _b in range(72)] for _c in range(5)]
    planets = gbotlib.categorize(galaxy, 'planets', True)
    fleets = gbotlib.categorize(galaxy, 'fleets')
    image_collections = [
        (0, planets['ally'], lambda x:x.ships),
        (1, planets['enemy'], lambda x:x.ships),
        (2, planets['neutral'], lambda x:x.ships),
        (3, fleets['ally'], lambda x:x.ships),
        (4, fleets['enemy'], lambda x:x.ships)
    ]
    
    for index, elist, value in image_collections:
        for entity in elist:
            fill_cross_points(
                round(entity.x/5 + 94/2),
                round(entity.y/5 + 72/2),
                round(entity.radius/5),
                min(value(entity) / 1000.0, 1.0),
                image[index]
            )
    return image
