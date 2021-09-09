import datetime
import math

import cv2
import pandas
import Telecontrol
from bokeh.plotting import figure, show, output_file
from bokeh.models import HoverTool, ColumnDataSource


# recursive function to find speed of telescope to track
def findSpeed(x, y, z):
    if abs(x) < y:
        findSpeed(x, y - 25, z - 1)
    else:
        return z

# Get request to get coordinates for telescope to point at ISS code will work only with internet
def jsonSat():
    import urllib.request
    import requests
    import pandas as pd

    # script for returning elevation from lat, long, based on latitude amd longitude data
    # which in turn is based on SRTM
    def get_elevation(lat, long):
        query = ('https://api.open-elevation.com/api/v1/lookup'
                 f'?locations={lat},{long}')
        r = requests.get(query).json()  # json object, various ways you can extract value
        # one approach is to use pandas json functionality:
        elevation = pd.json_normalize(r, 'results')['elevation'].values[0]
        print(elevation)
        return elevation

    # Get latitude and longitude of my location
    import geocoder
    g = geocoder.ip('me')
    print(g.latlng)

# Get altitude of location
    with urllib.request.urlopen(
            "http://geogratis.gc.ca/services/elevation/cdem/altitude?lat=" + str(g.latlng[0]) + "&lon=+" + str(
                    g.latlng[1])) as url:
        s = url.read()
       # check what is printed and see if necessary
       #  print(s)

    # if geogratis dosent work try function
    ele = get_elevation(g.latlng[0], g.latlng[1])
    # print(ele)

    # Get Azimuth and altitude
    # Request: /positions/{NORAD_id}/{observer_lat}/{observer_lng}/{observer_alt}/{seconds} example  Request:
    # e.g https://api.n2yo.com/rest/v1/satellite/positions/25544/41.702/-76.014/0/10/&apiKey=589P8Q-SDRYX8-L842ZD-5Z9
    print("https://api.n2yo.com/rest/v1/satellite/positions/25544/" + str(g.latlng[0]) + "/" + str(
        g.latlng[1]) + "/" + str(ele) + "/" + str(2) + "/&apiKey=FRRJZ2-SCGGM7-RXWBC9-4R5Y")
    with urllib.request.urlopen(
            "https://api.n2yo.com/rest/v1/satellite/positions/25544/" + str(g.latlng[0]) + "/" + str(
                    g.latlng[1]) + "/" + str(ele) + "/" + str(2) + "/&apiKey=FRRJZ2-SCGGM7-RXWBC9-4R5Y") as url:
        IssData = url.read()

        # print(s)
        return IssData

# collimation telescope and camera
import Collimation



# query from https://api.n2yo.com/rest/v1/satellite/
js = None
while js is  None:
    js = jsonSat()


import json

# parse js:
y = json.loads(js)
# print(y["positions"][0])
inf = y["positions"][0]

# get json attributes
azim = inf['azimuth']
alt = inf['elevation']
satT = inf['timestamp']

import time

t = int(time.time())
print("our time:"+str(t))
print("sat time:"+str(satT))

print(azim)
print(alt)

# Init telescope control
telescope = Telecontrol.Telcontrol()


# Set params for telescope to point to ISS trajectory
telescope.setAzimut(azim)
telescope.setAltitude(alt)


# Init tracking params
first_frame = None
status_list = [None, None]
times = []
df = pandas.DataFrame(columns=["Start", "End"])

# Turn on camera
video = cv2.VideoCapture(0)

# recording video param
width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
# recording details
writer = cv2.VideoWriter('basicvideo.mp4', cv2.VideoWriter_fourcc(*'DIVX'), 20, (width, height))


while True:

    # get feed from camera
    check, frame = video.read()

    # image manipultaion for maximizing differences between images
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # the command to record
    writer.write(frame)
    # if we our in the first frame there is nothiing to compare to -> continue to next iteration
    if first_frame is None:
        first_frame = gray
        continue

    # subtracting frames
    # finding the diffrences
    delta_frame = cv2.absdiff(first_frame, gray)
    # collecting the diffrences into one param 
    th_delta = cv2.threshold(delta_frame, 60, 255, cv2.THRESH_BINARY)[1]
    # removing the weak differences from the group we collected
    th_delta = cv2.dilate(th_delta, None, iterations=0)
    # finding the shapes around the differences
    (cnts, _) = cv2.findContours(th_delta.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in cnts:
        # the size of tracking we are looking to track
        # if cv2.contourArea(contour) < 10000:
        if cv2.contourArea(contour) < 5000:
            # the object is too small so we will skip to the next object that moves
            continue
            # color a rectangle around the moving object
        (x, y, w, h) = cv2.boundingRect(contour)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

        # center of image
        center = (w // 2, h // 2)

        # center of rectangle
        centerRec = ((x + w) // 2, (y + h) // 2)

        # direction vector
        xDir = w // 2 - (x + w) // 2
        yDir = h // 2 - (y + h) // 2

        # Here we add telescope control
        speedX = 7
        speedY = 7

        # find speed of telescope tracking according to distance from center
        speedX = findSpeed(xDir, 100, 7)
        speedY = findSpeed(yDir, 100, 7)


        # Move telescope in x and y direction
        telescope.moveX(xDir, speedX)
        telescope.moveY(yDir, speedY)

    # name of frame
    cv2.imshow('Capturing', frame)

    # exit tracking frame
    key = cv2.waitKey(1)
    if key == ord('q'):
        break

# exit camera feed and stop recording
video.release()
writer.release()
# close cv2 windows
cv2.destroyAllWindows()


