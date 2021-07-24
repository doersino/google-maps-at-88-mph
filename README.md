# google-maps-at-88-mph

The folks maintaining [Google Maps](https://www.google.com/maps) regularly update the satellite imagery it serves its users, but **outdated versions of the imagery are kept around in for a year or two**. This Python-based tool automatically crawls its way through these versions, figuring out which provide unique imagery and downloading it for a user-defined *(that's you! you get to define things!)* area, eventually **assembling it in the form of a GIF**.

*This weekend project is based on [ærialbot](https://github.com/doersino/aerialbot), a previous weekend project of mine.*

Scroll down to learn how to set it up on your machine, or stay up here for some examples.

There's usually two or three different views of any given area available in the "version history", which can yield neat 3D effects (the `<img title="">` attributes contain the invocations used to generate them):

TODO title attrs

<img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%">

For areas of the world that have changed significantly recently, flipping through the imagery versions is almost like a timelapse – consider the [port of Beirut](https://en.wikipedia.org/wiki/2020_Beirut_explosion) on the left, or TODO

<img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%">

Because Google regularly removes the oldest available versions, all of this is very ephemeral – a year from now, the invocations of this tool that have created the GIFs above may yield totally different results. Longer-term timelapses of the surface of our planet can be found on [Google Earth Timelapse](https://earthengine.google.com/timelapse/) *(or through [@earthacrosstime](https://twitter.com/earthacrosstime), another weekend project of mine, namely a Twitter bot of mine that posts randomly selected timelapses off it)*, but what's available there doesn't reach the high resolution of Google Maps.


## Setup

Being a good [Python 3](https://www.python.org) citizen, this tool integrates with `venv` to avoid dependency hell. (Although it only requires the `Pillow` and `requests` packages.) Run the following commands to get it installed on your system:

```bash
$ git clone https://github.com/doersino/google-maps-at-88-mph
$ python3 -m venv google-maps-at-88-mph
$ cd google-maps-at-88-mph
$ source bin/activate
$ pip3 install -r requirements.txt
```

(To deactivate the virtual environment, run `deactivate`.)


## Usage

Once you've set everything up, run the following command:

```bash
$ python3 googlemapsat88mph.py --help
```

That'll tell you in detail about the options. Most important are the three positional arguments:

1. The point you're interested in, along with
2. how wide (east-west extent) and...
3. ...how tall (north-south extent, both in meters) the downloaded area should be.

Along with those three, you need to supply a value for at least one of the `-m`, `-w`, and `-h` flags – the `--help` output explains them in detail.

For example, the following invocation will create the first of the GIFs embedded above, showing the White House:

TODO

TODO maybe screenshot/gif of cli in action

That's basically it!


## FAQ

### Why the name?

Because [when this baby hits 88 miles per hour, you're gonna see some serious shit](https://en.wikipedia.org/wiki/Back_to_the_Future).

### Why did you make this tool?

I became aware of how Google Maps versions its imagery as a side-effect of building and maintaining [ærialbot](https://github.com/doersino/aerialbot). Figuring out a way to explore past imagery seemed super interesting – note that initially, I wasn't sure how far back the available imagery would go. Finding out that it's only about a year was a bit of a letdown, but there's still some gems to be found either way. The ephemerality aspect also appeals to me.

### Does this violate Google's terms of use?

Probably. I haven't checked. But they haven't banned my IP for downloading tens of thousands of map tiles during development and testing (of ærialbot *and* this), so you're probably good as long as you don't use this tool for downloading a centimeter-scale map of your country. What's more, I can't think of a way in which this tool competes with or keeps revenue from any of Google's products. (And it's always worth keeping in mind that Google is an incredibly profitable company that earns the bulk of its income via folks like you just going about their days surfing the ad-filled web.)

### Something is broken – can you fix it?

Possibly. Please feel free to [file an issue](https://github.com/doersino/google-maps-at-88-mph/issues) – I'll be sure to take a look!
