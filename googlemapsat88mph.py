import io
import math
import os
import re
import random
import sys
import time
from datetime import datetime

import argparse

import concurrent.futures
import threading

import requests

from PIL import Image, ImageEnhance, ImageOps, ImageChops
Image.MAX_IMAGE_PIXELS = None


TILE_SIZE = 256  # in pixels
EARTH_CIRCUMFERENCE = 40075.016686 * 1000  # in meters, at the equator

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"


class WebMercator:
    """Various functions related to the Web Mercator projection."""

    @staticmethod
    def project(geopoint, zoom):
        """
        An implementation of the Web Mercator projection (see
        https://en.wikipedia.org/wiki/Web_Mercator_projection#Formulas) that
        returns floats. That's required for cropping of stitched-together tiles
        such that they only show the configured area, hence no use of math.floor
        here.
        """

        factor = (TILE_SIZE / (2 * math.pi)) * 2 ** (zoom - 8)  # -8 because 256 = 2^8
        x = factor * (math.radians(geopoint.lon) + math.pi)
        y = factor * (math.pi - math.log(math.tan((math.pi / 4) + (math.radians(geopoint.lat) / 2))))
        return (x, y)

class GeoPoint:
    """
    A latitude-longitude coordinate pair, in that order due to ISO 6709, see:
    https://stackoverflow.com/questions/7309121/preferred-order-of-writing-latitude-longitude-tuples
    """

    def __init__(self, lat, lon):
        assert -90 <= lat <= 90 and -180 <= lon <= 180

        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"GeoPoint({self.lat}, {self.lon})"

    def to_maptile(self, version, zoom):
        """
        Conversion of this geopoint to a tile through application of the Web
        Mercator projection and flooring to get integer tile corrdinates.
        """

        x, y = WebMercator.project(self, zoom)
        return MapTile(version, zoom, math.floor(x), math.floor(y))

    def compute_zoom_level(self, max_meters_per_pixel):
        """
        Computes the outermost (i.e. lowest) zoom level that still fulfills the
        constraint. See:
        https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
        """

        meters_per_pixel_at_zoom_0 = ((EARTH_CIRCUMFERENCE / TILE_SIZE) * math.cos(math.radians(self.lat)))

        # 23 seems to be highest zoom level supported anywhere in the world, see
        # https://stackoverflow.com/a/32407072 (although 19 or 20 is the highest
        # in many places in practice)
        for zoom in reversed(range(0, 23+1)):
            meters_per_pixel = meters_per_pixel_at_zoom_0 / (2 ** zoom)

            # once meters_per_pixel eclipses the maximum, we know that the
            # previous zoom level was correct
            if meters_per_pixel > max_meters_per_pixel:
                return zoom + 1
        else:

            # if no match, the required zoom level would have been too high
            raise RuntimeError("your settings seem to require a zoom level higher than is commonly available")

class GeoRect:
    """
    A rectangle between two points. The first point must be the southwestern
    corner, the second point the northeastern corner:
       +---+ ne
       |   |
    sw +---+
    """

    def __init__(self, sw, ne):
        assert sw.lat <= ne.lat
        # not assert sw.lon < ne.lon since it may stretch across the date line

        self.sw = sw
        self.ne = ne

    def __repr__(self):
        return f"GeoRect({self.sw}, {self.ne})"

    @classmethod
    def around_geopoint(cls, geopoint, width, height):
        """
        Creates a rectangle with the given point at its center. Like the random
        point generator, this accounts for high-latitude longitudes being closer
        together than at the equator. See also:
        https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
        """

        assert width > 0 and height > 0

        meters_per_degree = (EARTH_CIRCUMFERENCE / 360)

        width_geo = width / (meters_per_degree * math.cos(math.radians(geopoint.lat)))
        height_geo = height / meters_per_degree

        southwest = GeoPoint(geopoint.lat - height_geo / 2, geopoint.lon - width_geo / 2)
        northeast = GeoPoint(geopoint.lat + height_geo / 2, geopoint.lon + width_geo / 2)

        return cls(southwest, northeast)

class MapTileStatus:
    """An enum type used to keep track of the current status of map tiles."""

    PENDING = 1
    DOWNLOADING = 2
    DOWNLOADED = 3
    ERROR = 4

class MapTile:
    """
    A map tile: coordinates and, if it's been downloaded yet, image, plus some
    housekeeping stuff.
    """

    def __init__(self, version, zoom, x, y):  # TODO refactor order (also in repr)
        self.version = version
        self.zoom = zoom
        self.x = x
        self.y = y

        # initialize the other variables
        self.status = MapTileStatus.PENDING
        self.image = None

    def __repr__(self):
        return f"MapTile({self.version}, {self.zoom}, {self.x}, {self.y})"

    def load(self):
        """
        Downloads the tile image if it hasn't been downloaded yet. Can be used
        for retrying on errors.
        """

        if self.status != MapTileStatus.DOWNLOADED:
            self.download()


    def download(self):
        """
        Downloads a tile image. Sets the status to ERROR if things don't work
        out for whatever reason.
        """

        self.status = MapTileStatus.DOWNLOADING

        try:
            url_template = "https://khms2.google.com/kh/v={version}?x={x}&y={y}&z={zoom}"
            url = url_template.format(version=self.version, x=self.x, y=self.y, zoom=self.zoom)
            r = requests.get(url, headers={'User-Agent': USER_AGENT})
        except requests.exceptions.ConnectionError:
            self.status = MapTileStatus.ERROR
            return

        # error handling (note that a warning is appropriate here – if this tile
        # is one of a tiles used in imagery quality testing, an error is not an
        # unexpected outcome and should thus not be thrown)
        if r.status_code != 200:
            warning(f"Unable to download {self}, status code {r.status_code}.")
            self.status = MapTileStatus.ERROR
            return

        # convert response into an image
        data = r.content
        self.image = Image.open(io.BytesIO(data))

        # sanity check
        assert self.image.mode == "RGB"
        assert self.image.size == (TILE_SIZE, TILE_SIZE)

        # done!
        self.status = MapTileStatus.DOWNLOADED


class ProgressIndicator:
    """
    Displays and updates a progress indicator during tile download. Designed
    to run in a separate thread, polling for status updates frequently.
    """

    def __init__(self, maptilegrid):
        self.maptilegrid = maptilegrid

    def update_tile(self, maptile):
        """
        Updates a single tile depending on its state: pending tiles are grayish,
        downloading tiles are yellow, successfully downloaded tiles are green,
        and tiles with errors are red. For each tile, two characters are printed
        – in most fonts, this is closer to a square than a single character.
        See https://stackoverflow.com/a/39452138 for color escapes.
        """

        def p(s): print(s + "\033[0m", end='')

        if maptile.status == MapTileStatus.PENDING:
            p("░░")
        elif maptile.status == MapTileStatus.DOWNLOADING:
            p("\033[33m" + "▒▒")
        elif maptile.status == MapTileStatus.DOWNLOADED:
            p("\033[32m" + "██")
        elif maptile.status == MapTileStatus.ERROR:
            p("\033[41m\033[37m" + "XX")

    def update_text(self):
        """
        Displays percentage and counts only.
        """

        downloaded = 0
        errors = 0
        for maptile in self.maptilegrid.flat():
            if maptile.status == MapTileStatus.DOWNLOADED:
                downloaded += 1
            elif maptile.status == MapTileStatus.ERROR:
                errors += 1

        total = self.maptilegrid.width * self.maptilegrid.height
        percent = int(10 * (100 * downloaded / total)) / 10

        details = f"{downloaded}/{total}"
        if errors:
            details += f", {errors} error"
            if errors > 1:
                details += "s"


        # need a line break after it so that the first line of the next
        # iteration of the progress indicator starts at col 0
        print(f"{percent}% ({details})")

    def update(self):
        """Updates the progress indicator."""

        for y in range(self.maptilegrid.height):
            for x in range(self.maptilegrid.width):
                maptile = self.maptilegrid.at(x, y)
                self.update_tile(maptile)
            print()  # line break

        self.update_text()

        # move cursor back up to the beginning of the progress indicator for
        # the next iteration, see
        # http://www.tldp.org/HOWTO/Bash-Prompt-HOWTO/x361.html
        print(f"\033[{self.maptilegrid.height + 1}A", end='')

    def loop(self):
        """Main loop."""

        while any([maptile.status is MapTileStatus.PENDING or
                   maptile.status is MapTileStatus.DOWNLOADING
                   for maptile in self.maptilegrid.flat()]):
            self.update()
            time.sleep(0.1)
        self.update()  # final update to show that we're all done

    def cleanup(self):
        """Moves the cursor back to the bottom after completion."""

        print(f"\033[{self.maptilegrid.height}B")


class MapTileGrid:
    """
    A grid of map tiles, kepts as a nested list such that indexing works via
    [x][y]. Manages the download and stitching of map tiles into a preliminary
    result image.
    """

    def __init__(self, maptiles):
        self.maptiles = maptiles
        self.width = len(maptiles)
        self.height = len(maptiles[0])
        self.image = None

    def __repr__(self):
        return f"MapTileGrid({self.maptiles})"

    @classmethod
    def from_georect(cls, georect, zoom, version):
        """Divides a GeoRect into a grid of map tiles."""

        southwest = georect.sw.to_maptile(version, zoom)
        northeast = georect.ne.to_maptile(version, zoom)

        maptiles = []
        for x in range(southwest.x, northeast.x + 1):
            col = []

            # it's correct to have northeast and southwest reversed here (with
            # regard to the outer loop) since y axis of the tile coordinates
            # points toward the south, while the latitude axis points due north
            for y in range(northeast.y, southwest.y + 1):
                maptile = MapTile(version, zoom, x, y)
                col.append(maptile)
            maptiles.append(col)

        return cls(maptiles)

    def at(self, x, y):
        """Accessor with wraparound for negative values: x/y<0 => x/y+=w/h."""

        if x < 0:
            x += self.width
        if y < 0:
            y += self.height
        return self.maptiles[x][y]

    def flat(self):
        """Returns the grid as a flattened list."""

        return [maptile for col in self.maptiles for maptile in col]

    def download(self):
        """
        Downloads the constitudent tiles using a threadpool for performance
        while updating the progress indicator.
        """

        # set up progress indicator
        prog = ProgressIndicator(self)
        prog_thread = threading.Thread(target=prog.loop)
        prog_thread.start()

        # shuffle the download order of the tiles, this serves no actual purpose
        # but it makes the progress indicator look really cool!
        tiles = self.flat()
        random.shuffle(tiles)

        # download tiles using threadpool (2-10 times faster than
        # [maptile.load() for maptile in self.flat()]), see
        # https://docs.python.org/dev/library/concurrent.futures.html#threadpoolexecutor-example
        threads = max(self.width, self.height)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            {executor.submit(maptile.load): maptile for maptile in tiles}

        # retry failed downloads if fewer than 20% of tiles are missing
        missing_tiles = [maptile for maptile in self.flat() if maptile.status == MapTileStatus.ERROR]
        if 0 < len(missing_tiles) < 0.2 * len(self.flat()):
            print("Retrying missing tiles...")
            for maptile in missing_tiles:
                maptile.load()

        # finish up progress indicator
        prog_thread.join()
        prog.cleanup()

        # check if we've got everything now
        missing_tiles = [maptile for maptile in self.flat() if maptile.status == MapTileStatus.ERROR]
        if missing_tiles:
            raise RuntimeError(f"unable to download one or more map tiles: {missing_tiles}")

        # TODO instead of raising a runtime error, return something that will let main know things didn't work? break on 3 consecutive versions not working?

    def corners(self):
        """
        Returns a list of the four tiles in the corners of the grid. If the grid
        consists of only one or two tiles, they will occur multiple times.
        """

        return [self.at(x, y) for x in [0, -1] for y in [0, -1]]


    def cornersIdentical(self, other):
        self_corners = self.corners()
        other_corners = other.corners()

        diffs = 0
        for self_corner, other_corner in zip(self_corners, other_corners):
            self_corner.load()
            other_corner.load()

            # retry for good measure
            # TODO do this better?
            self_corner.load()
            other_corner.load()

            if self_corner.status == MapTileStatus.ERROR or other_corner.status == MapTileStatus.ERROR:
                raise RuntimeError("TODO error message")
                # TODO custom error (also in grid download function), handle gracefully in main

            diff = ImageChops.difference(self_corner.image, other_corner.image)
            diffs += sum([channel for pixel in list(diff.getdata()) for channel in pixel])
            print(sum([channel for pixel in list(diff.getdata()) for channel in pixel]))
            if sum([channel for pixel in list(diff.getdata()) for channel in pixel]) > 0:
                print(list(diff.getdata()))
                self_corner.image.save("test.jpg")
                other_corner.image.save("test2.jpg")
                diff.save("test3.png")
                #dfndfn

        # TODO improve this number?
        return diffs < 256 ** 2

        # TODO make sure the corners of both grids are downloaded
        # TODO compare with pillow and some error metric

    def stitch(self):
        """
        Stitches the tiles together. Must not be called before all tiles have
        been loaded.
        """

        image = Image.new('RGB', (self.width * TILE_SIZE, self.height * TILE_SIZE))
        for x in range(0, self.width):
            for y in range(0, self.height):
                image.paste(self.maptiles[x][y].image, (x * TILE_SIZE, y * TILE_SIZE))
        self.image = image


class MapTileImage:
    """Image cropping, resizing and enhancement."""

    def __init__(self, image):
        self.image = image

    def save(self, path, quality=90):
        self.image.save(path, quality=quality)

    def crop(self, zoom, georect):
        """
        Crops the image such that it really only covers the area within the
        input GeoRect. This function must only be called once per image.
        """

        return  # TODO# TODO# TODO# TODO# TODO# TODO# TODO# TODO# TODO

        sw_x, sw_y = WebMercator.project(georect.sw, zoom)
        ne_x, ne_y = WebMercator.project(georect.ne, zoom)

        # determine what we'll cut off
        sw_x_crop = round(TILE_SIZE * (sw_x % 1))
        sw_y_crop = round(TILE_SIZE * (1 - sw_y % 1))
        ne_x_crop = round(TILE_SIZE * (1 - ne_x % 1))
        ne_y_crop = round(TILE_SIZE * (ne_y % 1))

        # left, top, right, bottom
        crop = (sw_x_crop, ne_y_crop, ne_x_crop, sw_y_crop)

        # snip snap
        self.image = ImageOps.crop(self.image, crop)

    def scale(self, width, height):
        """
        Scales an image. This can distort the image if width and height don't
        match the original aspect ratio.
        """

        # Image.LANCZOS apparently provides the best quality, see
        # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#concept-filters
        self.image = self.image.resize((round(width), round(height)), resample=Image.LANCZOS)


def info(message):
    print(message)

def debug(message):
    if False:
        print(f"↪ {message}")

def warning(message):
    print(f"Warning: {message}")

def main():
    # TODO argument for most recent version? otherwise, how to get it?

    # handle potential cli arguments
    parser = argparse.ArgumentParser(add_help=False)
    # TODO description of what this program does
    # TODO need to explain what needs to be given and how the rest influences each other, see config.sample.ini
    parser.add_argument('point', metavar='LAT,LON', type=str, help='a point given as a latitude-longitude pair, e.g. \'37.453896,126.446829\'')
    parser.add_argument('--help', action='help', default=argparse.SUPPRESS, help=argparse._('show this help message and exit'))  # override default help argument so that only --help (and not -h) can call
    parser.add_argument('-m', '--max-meters-per-pixel', dest='max_meters_per_pixel', metavar='N', type=float, help='a maximum meters per pixel constraint that will override your configuration')
    parser.add_argument('-w', '--width', dest='width', metavar='N', type=float, help='width of the depicted area in meters, will override your configuration')
    parser.add_argument('-h', '--height', dest='height', metavar='N', type=float, help='height of the depicted area in meters, will override your configuration')
    parser.add_argument('--image_width', dest='image_width', metavar='N', type=float, help='width of the result image, will override your configuration (where you can also find an explanation of how this option interacts with the -m, -w, and -h options)')
    parser.add_argument('--image_height', dest='image_height', metavar='N', type=float, help='height of the result image, will override your configuration (where you can also find an explanation of how this option interacts with the -m, -w, and -h options)')
    args = parser.parse_args()

    info("Processing command-line options...")

    # copy the configuration into variables for brevity
    point = tuple(map(float, args.point.split(",")))
    p = GeoPoint(point[0], point[1])

    max_meters_per_pixel = None
    if args.max_meters_per_pixel:
        max_meters_per_pixel = args.max_meters_per_pixel

    width = None
    height = None
    if args.width:
        width = args.width
    if args.height:
        height = args.height

    image_width = None
    image_height = None
    if args.image_width:
        image_width = args.image_width
    if args.image_height:
        image_height = args.image_height

    ############################################################################

    info("Determining current Google Maps version (we'll work our way backwards from there)...")

    # automatic fallback: current as of July 2021, will likely continue
    # to work for at least a while
    current_version = '904'
    try:
        google_maps_page = requests.get("https://www.google.com/maps/", headers={'User-Agent': USER_AGENT}).content
        match = re.search(rb'khms0\.google\.com\/kh\/v\\u003d([0-9]+)', google_maps_page)
        if match:
            current_version = match.group(1).decode('ascii')
            debug(current_version)
        else:
            warning(f"Unable to extract current version, proceeding with outdated version {current_version} instead.")
    except requests.RequestException as e:
        warning(f"Unable to load Google Maps, proceeding with outdated version {current_version} instead.")
    current_version = int(current_version)

    # TODO if wasn't able to determine the current version, try working our way forward from outdated version based on map tile z=0x=0y=0?

    # process max_meters_per_pixel setting
    if image_width is None and image_height is None:
        assert max_meters_per_pixel is not None
    elif image_height is None:
        max_meters_per_pixel = (max_meters_per_pixel or 1) * (width / image_width)
    elif image_width is None:
        max_meters_per_pixel = (max_meters_per_pixel or 1) * (height / image_height)
    else:
        # if both are set, effectively use whatever imposes a tighter constraint
        if width / image_width <= height / image_height:
            max_meters_per_pixel = (max_meters_per_pixel or 1) * (width / image_width)
        else:
            max_meters_per_pixel = (max_meters_per_pixel or 1) * (height / image_height)

    # process image width and height for scaling
    if image_width is not None or image_height is not None:
        if image_height is None:
            image_height = height * (image_width / width)
        elif image_width is None:
            image_width = width * (image_height / height)

    info("Computing required tile zoom level at specified point...")
    zoom = p.compute_zoom_level(max_meters_per_pixel)
    debug(zoom)

    info("Generating rectangle with your selected width and height around point...")
    rect = GeoRect.around_geopoint(p, width, height)
    debug(rect)

    downloadedGrids = []
    downloadedImages = []
    for version in range(current_version, -1, -1):

        # TODO maybe prepend version to status messages here?

        info(f"Alrighty, prep work's done, trying version {version}...")
        # TODO only do the alrighty thing on the first iteration (or before entering the loop)

        info("Turning rectangle into a grid of map tiles at the required zoom level and for the current version...")
        grid = MapTileGrid.from_georect(rect, zoom, version)
        debug(grid)

        if version != current_version:
            # TODO improve message
            #info("Downloading the tiles at the corners and comparing with previously downloaded version...")
            info("Comparing corners with previously downloaded version...")
            # TODO compare against corners of all previously downloaded versions since sometimes rollback?
            if grid.cornersIdentical(downloadedGrids[-1]):
                info("Imagery seems identical, going to next version instead of downloading this one...")
                continue

        info("Downloading tiles...")
        grid.download()

        # TODO if errors: continue

        info("Stitching tiles together into an image...")
        grid.stitch()
        image = MapTileImage(grid.image)

        info("Cropping image to match the chosen area width and height...")
        debug((width, height))
        image.crop(zoom, rect)

        if image_width is not None or image_height is not None:
            info("Scaling image...")
            debug((image_width, image_height))
            image.scale(image_width, image_height)

        info("Saving image to disk...")
        image_path_template = "googlemaps-{datetime}-v{version}-x{xmin}..{xmax}y{ymin}..{ymax}-z{zoom}-{latitude},{longitude}-{width}x{height}m.jpg"
        image_path = image_path_template.format(
            datetime=datetime.today().strftime("%Y-%m-%dT%H.%M.%S"),
            version=version,
            xmin=grid.at(0, 0).x,
            xmax=grid.at(0, 0).x+grid.width,
            ymin=grid.at(0, 0).y,
            ymax=grid.at(0, 0).y+grid.height,
            zoom=zoom,
            latitude=p.lat,
            longitude=p.lon,
            width=width,
            height=height
        )
        debug(image_path)
        image_quality = 90
        image.save(image_path, image_quality)

        # keep track of TODO
        downloadedImages.append(image)

        # keep track of TODO
        downloadedGrids.append(grid)

        print(downloadedImages)

        # TODO if gif generation: make!
        # TODO unindent once error handling done, also status message
        # TODO proper filename
        # TODO maybe option for format: jpeg, gif, both. also gif framerate option
        # TODO => maybe class for "maptilegif"?
        downloadedImages[0].image.save("test.gif", append_images=[test.image for test in downloadedImages[1:]], save_all=True, duration=200, loop=0)

    info("All done!")


if __name__ == "__main__":
    main()





# TODO
# - more graceful termination (generally better error checking?, also for 4-corners?)
# - suppress debug output depending on verbose flag or something
#   maybe colorful status output
#   generally think about output
# - cull unnecessary bits of leftover code
# - write readme, promote on twitter (make a bot? nah...), etc.
#   explain 88 mph reference
#   screencapture of cli output
#   example gifs/mp4s: my hood, some place in the us, turkey cpi, something in korea or china
#   check how often versions change


# python3 googlemapsat88mph.py 48.471839,8.935646 -w 300 -h 300 -m 0.2 --image_width 500 --image_height 500
# python3 googlemapsat88mph.py "37.087214, 40.058665" -w 15000 -h 15000 -m 10
