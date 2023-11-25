from ratelimit import limits
import requests
import math
from PIL import Image
from dotenv import load_dotenv
import os
import slippymap_funcs
from io import BytesIO
import json
import argparse

def parse_arguments():

    arguments = {}

    parser = argparse.ArgumentParser()
    
    parser.add_argument('--tl', help='top left coordinates')
    parser.add_argument('--br', help='bottom left coorindates')
    parser.add_argument('--zscale', default=1, help='multiplier for z axis, default 1')
    parser.add_argument('--zoom', default=10, help='zoom level based on size of area, default 10')

    args = parser.parse_args()

    if ',' not in args.tl or ',' not in args.br:
        print('Co-ordinates format should be lat,lon . Format not recognised')

    if not args.tl or not args.br:
        print('Missing top left coords (--tl), or bottom right coords (--br)')
        exit()

    comma_index = args.tl.index(',')
    arguments['tl_lat'] = float(args.tl[0 : comma_index])
    arguments['tl_lon'] = float(args.tl[(comma_index + 1): len(args.tl)])

    comma_index = args.br.index(',')
    arguments['br_lat'] = float(args.br[0 : comma_index])
    arguments['br_lon'] = float(args.br[(comma_index + 1): len(args.tl)])

    arguments['z_scale_factor'] = float(args.zscale)
    arguments['zoom'] = int(args.zoom)

    return arguments

class Mesh:

    def __init__(self):
        load_dotenv()
        self.ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
        self.format = "pngraw"
        self.tileset_id = "mapbox.mapbox-terrain-dem-v1"


    @limits(calls=30, period=10)
    def api_call(self, x, y):

        url = f"https://api.mapbox.com/v4/{self.tileset_id}/{self.zoom}/{x}/{y}@2x.{self.format}?access_token={self.ACCESS_TOKEN}"

        image = requests.get(url)

        if image.status_code == 404:
            im = self.seaTile(self)
        else:
            im = Image.open(BytesIO(image.content))

        return(im)


    def seaTile(self):

        seaTile = Image.new('RGB', ((self.tileSize), (self.tileSize)), (1,134,160))

        return seaTile


    def create_image(self):

        # defining scale factor so that elevation looks correct based upon the scale of the image, uses average latitude in case area is tall and thin

        # circumference of the earth at the equator in metres
        C = 40075016.686 

        avgLat = (self.TLLat + self.BRLat) / 2
        self.pxDist = (C * math.cos(math.radians(avgLat)) / (2**self.zoom)) / self.tileSize

        fullImage = Image.new('RGB', ((self.tilesWidth*self.tileSize), (self.tilesHeight*self.tileSize)), (250,250,250))

        return(fullImage)

    def validate(self, TLLat: float, TLLon: float, BRLat: float, BRLon: float, zoom: int, x2=False):

        # TODO add exception to this data val for longitude that crosses international dateline
        # TODO check mapbox API latitude extremes and add validation for this

        # coordinate data validation, checks correct data type has been provided, and checks top left and bottom right coordinates align

        coords = {"Top Left Lat": TLLat, "Top Left Lon": TLLon, "Bottom Right Lat": BRLat, "Bottom Right Lon": BRLon}

        for name, coord in coords.items():
            if isinstance(coord, (int, float)) == False:
                raise TypeError(f'Error ({name}): Expected int or float, received {type(coord).__name__}')

        if TLLat <= BRLat:
            raise ValueError('Error: Top left latitude must be north of bottom right latitude')

        if TLLon >= BRLon:
            raise ValueError('Error: Top left longitude must be west of bottom right longitude')
        
        #checking if zoom is int and then if it is in accepted range (>= 0 and <= 15) as data over zoom level of 15 is useless for purpose of script

        if isinstance(zoom, int) == False:
            raise TypeError(f'Error (Zoom): Expected int, received {type(zoom).__name__}')

        if type(zoom) == bool:
            raise TypeError(f'Error (Zoom): Expected int, received {type(zoom).__name__}')

        if zoom < 0 or zoom >= 15:
            raise ValueError(f'Error: Zoom level should be between 0 and 15 (Given: {zoom})')

        #checks if x2 argument is bool (default = false, can be set to true)

        if not type(x2) == bool:
            raise TypeError(f'Error (x2): Expected bool, received {type(x2).__name__}')


    @staticmethod
    def generate_data(self, TLLat: float, TLLon: float, BRLat: float, BRLon: float, zoom: int, x2=False):

        #runs init in case there is no instance of class

        self.__init__(self)

        #performs basic data validation

        print('Validating data')
        try:
            self.validate(self, TLLat, TLLon, BRLat, BRLon, zoom, x2)
        except ValueError as error:
            print(error)
            exit()
        except TypeError as error:
            print(error)
            exit()
        
        print('Data provided is valid')

        #variable assignment

        self.TLLat = TLLat
        self.TLLon = TLLon
        self.BRLat = BRLat
        self.BRLon = BRLon
        self.zoom = zoom

        #setting tileSize (in pixels) to the specified value

        self.tileSize = 512 if x2 == True else 256

        #calculate size of area in tiles

        self.origin = slippymap_funcs.deg2num(self.TLLat, self.TLLon, self.zoom)
        self.limit = slippymap_funcs.deg2num(self.BRLat, self.BRLon, self.zoom)

        #calculates the height / width of the requested area in tiles

        self.tilesWidth = abs(self.limit[0] - self.origin[0]) + 1
        self.tilesHeight = abs(self.limit[1] - self.origin[1]) + 1

        # check for many tiles to stop making many api calls

        self.totalTiles = self.tilesWidth * self.tilesHeight
        if self.totalTiles > 20:
            response = input(f'Request will query {self.totalTiles} tiles. Proceed (y/n)? ')
            if response == 'y':
                print('Running algorithm')
            else:
                print('Aborting')
                exit()       
        
        # creates dictionary for coordinate values
        
        self.tiles = { (0,0) : 0 }

        #these 4 variables are trackers that are only used in the while loops directly below
        tilex = 0
        tiley = 0
        originx = self.origin[0]
        originy = self.origin[1]

        while tilex < self.tilesWidth:
            while tiley < self.tilesHeight:

                self.tiles[(tilex, tiley)] = (originx, originy)

                originy +=1
                tiley += 1
            originx += 1
            tilex += 1
            originy = self.origin[1]
            tiley = 0
            
        # creates full image so that tiles can be pasted into it

        self.fullImage = self.create_image(self)

        # now we need to make the api call to retrieve the data

        for key, tile in self.tiles.items():

            x = tile[0]
            y = tile[1]
            pngx = key[0] * self.tileSize
            pngy = key[1] * self.tileSize

            image = self.api_call(self, x, y)

            self.fullImage.paste(image, (pngx, pngy))

        # next, we need to calculate the edges of the requested area (up until now the request was just tiles). this allows us to crop to the correct size

        trim1 = slippymap_funcs.deg2numFloat(self.TLLat, self.TLLon, zoom)
        trim2 = slippymap_funcs.deg2numFloat(self.BRLat, self.BRLon, zoom)

        # calculates pixel coordinates for left, top, right, bottom of requested coordinates

        left = round(((trim1[0] - self.origin[0]) * 512))
        top = round(((trim1[1] - self.origin[1]) * 512))

        right = round(((trim2[0] - self.limit[0]) * 512) + ((self.tilesWidth - 1) * 512))
        bottom = round(((trim2[1] - self.limit[1]) * 512)+ ((self.tilesHeight - 1) * 512))

        self.fullImage = self.fullImage.crop((left, top, right, bottom))

        self.fullImage.save('result.png', 'png')

        return(self.fullImage)