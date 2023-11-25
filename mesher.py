from mapboxAPI import Mesh, parse_arguments
from PIL import Image
import openmesh as om

args = parse_arguments()
print(f'Generating heightmap for TL: {args["tl_lat"]},{args["tl_lon"]}, BR: {args["br_lat"]},{args["br_lon"]}, ZScale = {args["z_scale_factor"]}, Zoom = {args["zoom"]}')

data = Mesh.generate_data(Mesh, args['tl_lat'], args['tl_lon'], args['br_lat'], args['br_lon'], args['zoom'], True)

# converts image to pixel values for elevation calculation
px = data.convert('RGB')

# creating polymesh for data to go into
mesh = om.PolyMesh()

# these variables are set so to provide limits for the while loop that creates all verts
imSize = data.size
imageX = imSize[0]
imageY = imSize[1]

# shows the x and y distance of the defined area (variables are unused but can be used for stats later on)
areaX = Mesh.pxDist * imSize[0]
areaY = Mesh.pxDist * imSize[1]

# these variables are used to track the pixels in the image and create the verts
# there is a pixelx, pixely and x, y because the pixels originate from top left, and we want to originate from bottom left
pixelx = 0
pixely = (imSize[1] - 1)
verts = { (0,0) : 0}
x = 0
y = 0

# while loop to create all verts
while pixelx < imageX:

    while pixely >= 0:

        r, g, b = px.getpixel((pixelx, pixely))

        elev = ((-10000 + ((r * 256 * 256 + g * 256 + b) * 0.1)) / Mesh.pxDist) * args['z_scale_factor']

        # if elev > 0:
        #     elev = elev + 1

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