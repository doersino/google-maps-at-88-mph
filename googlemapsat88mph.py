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

from PIL import Image, ImageOps, ImageChops
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

    def __init__(self, version, zoom, x, y):
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
            r = requests.get(url, headers={"User-Agent": USER_AGENT})
        except requests.exceptions.ConnectionError:
            self.status = MapTileStatus.ERROR
            return

        # error handling
        if r.status_code != 200:
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

        def p(s): print(s + "\033[0m", end="")

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
        print(f"\033[{self.maptilegrid.height + 1}A", end="")

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


class MissingTilesError(Exception):
    """Exception raised when a MapTileGrid couldn't be completely downloaded."""

    def __init__(self, message, missing, total):
        self.message = message
        self.missing = missing
        self.total = total

    def __str__(self):
        return self.message

class MapTileGrid:
    """
    A grid of map tiles, kepts as a nested list such that indexing works via
    [x][y]. Manages the download and stitching of map tiles into a preliminary
    result image.
    """

    def __init__(self, maptiles, version):
        self.maptiles = maptiles
        self.version = version

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

        return cls(maptiles, version)

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
            raise MissingTilesError(f"unable to download one or more map tiles", len(missing_tiles), len(self.flat()))

    def corners(self):
        """
        Returns a list of the four tiles in the corners of the grid. If the grid
        consists of only one or two tiles, they will occur multiple times.
        """

        return [self.at(x, y) for x in [0, -1] for y in [0, -1]]


    def corners_identical_to(self, other):
        """
        Checks whether the four corners of this grid are identical to the ones
        from another grid. The other grid must already be fully loaded (or, at
        least, there corners must be present).
        """

        self_corners = self.corners()
        other_corners = other.corners()

        # download self's corners
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            {executor.submit(maptile.load): maptile for maptile in self_corners}

        # rety
        missing_tiles = [maptile for maptile in self_corners if maptile.status == MapTileStatus.ERROR]
        for maptile in missing_tiles:
            maptile.load()
        missing_tiles = [maptile for maptile in self_corners if maptile.status == MapTileStatus.ERROR]
        if missing_tiles:
            raise MissingTilesError(f"unable to download one or more corner tiles", len(missing_tiles), len(self_corners))

        # super basic difference metric: just sum up the differences of each
        # channel for every pixel (for every corner) – you'd think this would be
        # slow, but it takes 0.2s on my 2015 machine for all four combined (the
        # download is the slow part!)
        for self_corner, other_corner in zip(self_corners, other_corners):
            diff = ImageChops.difference(self_corner.image, other_corner.image)
            if any([True for channels in list(diff.getdata()) if channels != (0,0,0)]):
                return False

        return True

    def stitch(self):
        """
        Stitches the tiles comprising this grid together. Must not be called
        before all tiles have been loaded.
        """

        image = Image.new("RGB", (self.width * TILE_SIZE, self.height * TILE_SIZE))
        for x in range(0, self.width):
            for y in range(0, self.height):
                image.paste(self.maptiles[x][y].image, (x * TILE_SIZE, y * TILE_SIZE))
        self.image = image


class MapTileImage:
    """Image cropping, resizing and enhancement."""

    def __init__(self, image, version):
        self.image = image
        self.version = version

    def save(self, path, quality=90):
        self.image.save(path, quality=quality)

    def crop(self, zoom, georect):
        """
        Crops the image such that it really only covers the area within the
        input GeoRect. This function must only be called once per image.
        """

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


class Printer:
    def __init__(self, verbose):
        self.verbose = verbose

    def head(self, message):
        print(f"\033[1m{message}\033[0m")

    def info(self, message):
        print(message)

    def debug(self, message):
        if self.verbose:
            print(f"\033[2m{message}\033[0m")

    def warn(self, message):
        print(f"\033[35m{message}\033[0m")

def main():
    parser = argparse.ArgumentParser(
        add_help=False,  # avoid adding the automatic '-h' and '--help' options
                         # since '-h' is needed for specifying the image height
        description="Google Maps regularly updates the satellite imagery it serves its users, but outdated versions of the imagery are kept around for a year or two. This tool automatically crawls its way through these versions, figuring out which provide unique imagery and downloading it for a user-defined \033[3m(that's you! you get to define things!)\033[0m area, eventually assembling it in the form of a GIF. Based on ærialbot (see https://github.com/doersino/aerialbot). Requires the \033[3mPillow\033[0m and \033[3mrequests\033[0m libraries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter  # show defaults
    )

    optional = parser.add_argument_group("Optional arguments")

    # override default help argument so that only --help (and not -h) can call
    optional.add_argument("--help",
        default=argparse.SUPPRESS,
        action="help",
        help="Show this message and exit."
    )
    optional.add_argument("-v", "--verbose",
        default=argparse.SUPPRESS,
        action="store_true",
        help="Output debug information while running."
    )
    optional.add_argument("--version",
        dest="current_version",
        metavar="N",
        type=int,
        default=904,  # current as of July 2021
        help="Current Google Maps version. This tool tries to determine it automatically, but if that fails (due to a changes on Google's end, for instance), you can override the likely-outdated default/fallback: Navigate to Google Maps in your browser, open its developer tools, and search the HTML source code of the page for the string 'khms0.google.com/kh/v\\u003d'. The number right after the 'd' is the current version."
    )

    pointy = parser.add_argument_group("Point of interest")
    pointy.add_argument("point",
        metavar="LAT,LON",
        type=str,
        help="\033[1mRequired.\033[0m Specified as a latitude-longitude pair, \033[3me.g.\033[0m, '37.453896,126.446829'. (Be aware that negative latitudes yield argument parsing errors unless you wrap the point, preceded with a space, in quotes, \033[3me.g.\033[0m, ' -51.699730,-57.852601'.)"
    )

    area = parser.add_argument_group("Area definition",
        description="Some explanation of these arguments is in order: You \033[3mneed\033[0m to specify width and height. You can also specify a maximum meters per pixel constraint – see below – but you don't have to if image width or height are specified (note that if neither is, the resulting image dimensions vary by latitude), the maximum meters per pixel constraint can be automatically derived in this case. Only image width \033[3mor\033[0m height is required, the other will be computed. Note that if you set \033[3mboth\033[0m image width and height but they don't match the aspect ratio of the area, things will look squished."
    )
    area.add_argument("width",
        metavar="WIDTH",
        type=float,
        default=argparse.SUPPRESS,
        help="\033[1mRequired.\033[0m Width of the depicted area in meters."
    )
    area.add_argument("height",
        metavar="HEIGHT",
        type=float,
        default=argparse.SUPPRESS,
        help="\033[1mRequired.\033[0m Height of the depicted area in meters."
    )
    area.add_argument("-m", "--max-meters-per-pixel",
        dest="max_meters_per_pixel",
        metavar="N",
        type=float,
        default=argparse.SUPPRESS,
        help="Maximally allowable meters contained in a single pixel of the result image (\033[3mafter\033[0m scaling to image width and height), determines the required tile zoom level, setting it as coarse as possible (to conserve bandwidth and processing overhead) while still fulfilling this constraint."
    )
    area.add_argument("-w", "--image-width",
        dest="image_width",
        metavar="N",
        type=float,
        default=argparse.SUPPRESS,
        help="Width of the result image in pixels."
    )
    area.add_argument("-h", "--image-height",
        dest="image_height",
        metavar="N",
        type=float,
        default=argparse.SUPPRESS,
        help="Height of the result image in pixels."
        )

    output = parser.add_argument_group("Output configuration",
        description="All files will be output in the current directory. Note that, as opposed to how it's done in ærialbot, map tiles aren't persisted to the file system."
    )
    output.add_argument("-f", "--format",
        dest="output_format",
        type=str,
        choices=["jpegs", "gif", "both"],
        default="both",
        help="Output format: 'jpegs' will output a bunch of JPEGs, 'gif' will collect them into a GIF instead (with the usual fidelity and filesize implications), 'both' will do both."
    )
    output.add_argument("-q", "--quality",
        type=int,
        default=90,
        help="JPEG compression quality (0-100), only relevant if JPEGs are emitted."
    )
    output.add_argument("-r", "--framerate",
        type=float,
        default=3,
        help="Number of frames per second, only relevant if GIFs are emitted."
    )
    output.add_argument("-s", "--simpler-filenames",
        dest="simpler_filenames",
        default=argparse.SUPPRESS,
        action="store_true",
        help="The default output filenames contain a bunch of redundant information because I, the author of this tool, thought it might come in handy. Pass this flag for admittedly saner filenames."
    )

    # parse arguments
    args = parser.parse_args()

    # initialize status messages printer
    verbose = hasattr(args, "verbose")
    printer = Printer(verbose)

    printer.info("Processing command-line options...")
    printer.debug(args)

    # process options
    point = tuple(map(float, args.point.split(",")))
    p = GeoPoint(point[0], point[1])

    current_version = args.current_version

    max_meters_per_pixel = None
    if hasattr(args, "max_meters_per_pixel"):
        max_meters_per_pixel = args.max_meters_per_pixel

    width = None
    height = None
    if hasattr(args, "width"):
        width = args.width
    if hasattr(args, "height"):
        height = args.height

    image_width = None
    image_height = None
    if hasattr(args, "image_width"):
        image_width = args.image_width
    if hasattr(args, "image_height"):
        image_height = args.image_height

    output_format = args.output_format
    quality = args.quality
    framerate = args.framerate

    image_path_template = "googlemapsat88mph-{datetime}-v{versions}-x{xmin}..{xmax}y{ymin}..{ymax}-z{zoom}-{latitude},{longitude}-{width}x{height}m"
    if hasattr(args, "simpler_filenames"):
        image_path_template = "googlemapsat88mph-lat{latitude}-lon{longitude}-width{width}m-height{height}m-versions{versions}"

    # process max_meters_per_pixel option
    if image_width is None and image_height is None:
        if max_meters_per_pixel is None:
            raise ValueError("neither image height nor width given, so a maximum meters per pixel constraint needs to be specified")
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

    ############################################################################

    printer.info("Determining current Google Maps version (we'll work our way backwards from there)...")

    # automatic fallback: current as of July 2021, will likely continue
    # to work for at least a while
    try:
        google_maps_page = requests.get("https://maps.googleapis.com/maps/api/js", headers={"User-Agent": USER_AGENT}).content
        match = re.search(rb"khms0\.googleapis\.com\/kh\?v=([0-9]+)", google_maps_page)
        if match:
            current_version = int(match.group(1).decode("ascii"))
            printer.debug(current_version)
        else:
            printer.warn(f"Unable to extract current version, proceeding with outdated version {current_version} instead.")
    except requests.RequestException:
        printer.warn(f"Unable to load Google Maps, proceeding with outdated version {current_version} instead.")

    printer.info("Computing required tile zoom level at specified point...")
    zoom = p.compute_zoom_level(max_meters_per_pixel)
    printer.debug(zoom)

    printer.info("Generating rectangle with your selected width and height around point...")
    rect = GeoRect.around_geopoint(p, width, height)
    printer.debug(rect)

    ############################################################################

    printer.info("Alrighty, prep work's done!")

    previousGrid = None
    downloadedImages = []
    for version in range(current_version, -1, -1):
        try:
            printer.head(f"Version {version}")

            printer.info("Turning rectangle into a grid of map tiles at the required zoom level and for the current version...")
            grid = MapTileGrid.from_georect(rect, zoom, version)
            printer.debug(grid)

            # if we're not on the first iteration, check if the imagery differs at the corners
            if version != current_version:
                printer.info("Downloading corner tiles and comparing with previously downloaded version...")
                if grid.corners_identical_to(previousGrid):
                    printer.info("Imagery seems identical, going to next version instead of downloading this one...")
                    continue

            previousGrid = grid

            printer.info("Downloading tiles...")
            grid.download()

            printer.info("Stitching tiles together into an image...")
            grid.stitch()
            image = MapTileImage(grid.image, version)

            printer.info("Cropping image to match the chosen area width and height...")
            printer.debug((width, height))
            image.crop(zoom, rect)

            if image_width is not None or image_height is not None:
                printer.info("Scaling image...")
                printer.debug((image_width, image_height))
                image.scale(image_width, image_height)

            if output_format != "gif":
                printer.info("Saving image to disk...")

                image_path = (image_path_template + ".jpg").format(
                    datetime=datetime.today().strftime("%Y-%m-%dT%H.%M.%S"),
                    versions=version,
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
                printer.debug(image_path)
                image_quality = quality
                image.save(image_path, image_quality)

            # keep track of downloaded images for gif writing
            downloadedImages.append(image)

        except MissingTilesError as e:

            # provide a good error message if not even the ostensibly-current
            # version could be downloaded
            if version == current_version:
                raise RuntimeError("couldn't download the current version – either your connection's wonky or that version doesn't exist")

            # if only some tiles are missing, the version does exists but the
            # connection's wonky – but if all are missing, either the
            # connection's dead or that was it
            if (e.missing != e.total):
                raise e
            else:
                printer.info(f"It appears as though version {version} has been purged, or your internet connection has disappeared – either way, this is the end of the line.")

                if output_format != "jpeg":

                    # reverse downloaded images list to proceed from oldest to newest
                    downloadedImages.reverse()

                    printer.info("Writing GIF...")
                    image_path = (image_path_template + ".gif").format(
                        datetime=datetime.today().strftime("%Y-%m-%dT%H.%M.%S"),
                        versions=",".join(map(lambda i: str(i.version), downloadedImages)),
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
                    downloadedImages[0].image.save(image_path, append_images=[i.image for i in downloadedImages[1:]], save_all=True, duration=1000/framerate, loop=0)
                    printer.debug(image_path)

                printer.info("All done! 🛰")

                # exit the loop (thereby terminate the program)
                break

if __name__ == "__main__":
    main()
