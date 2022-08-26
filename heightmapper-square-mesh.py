import requests
import math
from PIL import Image
from io import BytesIO
import numpy as np
import openmesh as om
from ratelimiter import RateLimiter
import os
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')

def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  xtile = int((lon_deg + 180.0) / 360.0 * n)
  ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
  return (xtile, ytile)

def deg2numFloat(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  xtile = (lon_deg + 180.0) / 360.0 * n
  ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
  return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
  n = 2.0 ** zoom
  lon_deg = xtile / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
  lat_deg = math.degrees(lat_rad)
  return (lat_deg, lon_deg)

@RateLimiter(max_calls=30, period=10)
def apiCall(x, y, zoom):
    url = f"https://api.mapbox.com/v4/{tileset_id}/{zoom}/{x}/{y}@2x.{format}?access_token={ACCESS_TOKEN}"
    image = requests.get(url)
    if image.status_code == 404:
        im = seaTile()
    else:
        im = Image.open(BytesIO(image.content))
    return(im)

def seaTile():
    seaTile = Image.new('RGB', ((tileSize), (tileSize)), (1,134,160))
    return seaTile

#origin and limit are top left and bottom right corners of chosen area

# # Kent
# originLat = 51.332971750327076
# originLon = 0.9723738188144215
# limitLat = 51.05043628202769
# limitLon = 1.4677055776360717

# zoom = 10

# # UK
# originLat = 59.45441906729533
# originLon = -12.254052707296019
# limitLat = 49.678121214543395
# limitLon = 2.6842068985081435

# zoom = 1

originLat = 75.70025198684874
originLon = -165.97342064511028
limitLat = -59.412709082314834
limitLon = 178.65023928540245

zoom = 3

#calculate size of area in tiles
origin = deg2num(originLat, originLon, zoom)
limit = deg2num(limitLat, limitLon, zoom)

# creates dictionary for coordinate values
tiles = { (0,0) : 0 }

#calculates the height / width of the requested area in tiles
width = abs(limit[0] - origin[0]) + 1
height = abs(limit[1] - origin[1]) + 1

# check for many tiles to stop making many api calls
totalTiles = width * height
if totalTiles > 20:
    response = input(f'Request will query {totalTiles} tiles. Proceed (y/n)? ')
    if response == 'y':
        print('Running algorithm')
    else:
        print('Aborting')
        exit()


#these 4 variables are trackers that are only used in the while loops directly below
tilex = 0
tiley = 0
originx = origin[0]
originy = origin[1]

while tilex < width:
    while tiley < height:

        tiles[(tilex, tiley)] = (originx, originy)

        originy +=1
        tiley += 1
    originx += 1
    tilex += 1
    originy = origin[1]
    tiley = 0

# next, we need to create the full image for desired area
tileSize = 512

# defining scale factor so that elevation looks correct based upon the scale of the image, uses average latitude in case area is tall and thin
C = 40075016.686
avgLat = (originLat + limitLat) / 2
pxDist = (C * math.cos(math.radians(51.33)) / (2**zoom)) / tileSize

fullImage = Image.new('RGB', ((width*tileSize), (height*tileSize)), (250,250,250))

#api values

tileset_id = "mapbox.mapbox-terrain-dem-v1"
format = "pngraw"

# api calls happen here in loop

for key, tile in tiles.items():
    x = tile[0]
    y = tile[1]
    pngx = key[0] * tileSize
    pngy = key[1] * tileSize

    image = apiCall(x, y, zoom)

    fullImage.paste(image, (pngx, pngy))

# next, we need to calculate the edges of the requested area (up until now the request was just tiles). this allows us to crop to the correct size

trim1 = deg2numFloat(originLat, originLon, zoom)
trim2 = deg2numFloat(limitLat, limitLon, zoom)

left = round(((trim1[0] - origin[0]) * 512))
top = round(((trim1[1] - origin[1]) * 512))

right = round(((trim2[0] - limit[0]) * 512) + ((width - 1) * 512))
bottom = round(((trim2[1] - limit[1]) * 512)+ ((height - 1) * 512))

fullImage = fullImage.crop((left, top, right, bottom))
fullImage.save('result.png', 'png')
# fullImage.show()

# converts image to pixel values for elevation calculation
px = fullImage.convert('RGB')

# creating polymesh for data to go into
mesh = om.PolyMesh()

# these variables are set so to provide limits for the while loop that creates all verts
imSize = fullImage.size
imageX = imSize[0]
imageY = imSize[1]

# shows the x and y distance of the defined area (variables are unused but can be used for stats later on)
areaX = pxDist * imSize[0]
areaY = pxDist * imSize[1]

# these variables are used to track the pixels in the image and create the verts
# there is a pixelx, pixely and x, y because the pixels originate from top left, and we want to originate from bottom left
pixelx = 0
pixely = (imSize[1] - 1)
verts = { (0,0) : 0}
x = 0
y = 0

zScaleFactor = 15

# while loop to create all verts
while pixelx < imageX:

    while pixely >= 0:

        r, g, b = px.getpixel((pixelx, pixely))

        elev = ((-10000 + ((r * 256 * 256 + g * 256 + b) * 0.1)) / pxDist) * zScaleFactor

        verts[(x, y)] = mesh.add_vertex([x, y, elev])

        pixely -= 1
        y += 1

    pixelx += 1
    pixely = imSize[1] - 1
    x += 1
    y = 0

# this while loop creates all the faces from the vertices previously defined

x = 0
y = 0

while x < imageX:

    while y < imageY:

        if x < (imageX-1) and y < (imageY-1):

            face = mesh.add_face(verts[(x, y)], verts[(x, y+1)], verts[(x+1, y+1)], verts[(x+1, y)])
            
        y += 1

    x += 1
    y = 0

om.write_mesh('result.obj', mesh)
