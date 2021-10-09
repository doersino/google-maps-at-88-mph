# google-maps-at-88-mph

The folks maintaining [Google Maps](https://www.google.com/maps) regularly update the satellite imagery it serves its users, but **outdated versions of the imagery are kept around for a year or two**. This Python-based tool automatically crawls its way through these versions, figuring out which provide unique imagery and downloading it for a user-defined *(that's you! you get to define things!)* area, eventually **assembling it in the form of a GIF**.

*This weekend project is based on [ærialbot](https://github.com/doersino/aerialbot), a previous weekend project of mine.*

Scroll down to learn how to set it up on your machine, or stay up here for some examples.

There's usually two or three different views of any given area available in the "version history", which can yield neat 3D effects (the `<img title="">` attributes contain the invocations used to generate them):

<img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" title="python3 googlemapsat88mph.py 38.900068,-77.036555 1000 1000 -w 500" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T22.13.07-v877,903,904-x68787..68791y45301..45305-z17-48.474655,8.934258-500.0x500.0m.gif" title="python3 googlemapsat88mph.py 48.474655,8.934258 500 500 -w 500" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T22.32.40-v865,893,904-x107054..107058y57064..57069-z17-22.648492,114.037832-1000.0x1000.0m.gif" title="python3 googlemapsat88mph.py 22.648492,114.037832 1000 1000 -w 500" width="32%">

For areas of the world that have changed significantly recently, flipping through the imagery versions is almost like a timelapse – consider the port of Beirut before and after the [2020 explosion](https://en.wikipedia.org/wiki/2020_Beirut_explosion) on the left, or the perpetually-over-budget-and-behind-schedule construction of the new [Stuttgart central station](https://en.wikipedia.org/wiki/Stuttgart_Hauptbahnhof) on the right.

<img src="demo/googlemapsat88mph-2021-07-24T22.19.39-v873,875,904-x39231..39237y26199..26203-z16-33.900646,35.518118-2297.0x1500.0m.gif" title="python3 googlemapsat88mph.py 33.900646,35.518118 2297 1500 -h 500" width="49%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T22.24.29-v877,888,904-x137756..137762y90264..90268-z18-48.783753,9.183353-459.5x300.0m.gif" title="python3 googlemapsat88mph.py 48.783753,9.183353 459.5 300 -h 500" width="49%">

It's also fun to look at airports and [center pivot irrigation fields](https://www.youtube.com/playlist?list=PLTphPoE54a1s_ZdCkGwbhQO9O5SMSitA1) through the lens this tool provides:

<img src="demo/googlemapsat88mph-2021-07-24T22.39.30-v864,867,868,872,873,877,882,888,891,897,903,904-x38482..38486y27014..27018-z16-30.106566,31.398192-1200.0x1200.0m.gif" title="python3 googlemapsat88mph.py 30.106566,31.398192 1200 1200 -h 500" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T22.44.43-v897,904-x33634..33638y21554..21557-z16-52.309827,4.766492-1000.0x1000.0m.gif" title="python3 googlemapsat88mph.py 52.309827,4.766492 1000 1000 -h 500" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-25T14.51.11-v867,872,873,875,877,878,882,888,904-x20009..20013y12776..12780-z15-36.79054,39.848536-3000.0x3000.0m.gif" title="python3 googlemapsat88mph.py 36.79054,39.848536 3000 3000 -w 500" width="32%">

As an alternative to the usual straight-down imagery, which is great for navigating but obscures the verticality of buildings and structures, Google Maps also provides *oblique* views shot at a 45-degree angle – from all of the four cardinal directions – for many urban areas. This kind of imagery looks great wherever skyscrapers are around – say, in New York City:

<img src="demo/googlemapsat88mph-2021-10-09T21.19.54-northward-v128,131-x77152..77156y108097..108101-z18-40.6895661149898,-74.04479028328522-300.0x577.0m.gif" title="python3 googlemapsat88mph.py 40.6895661149898,-74.04479028328522 300 577 -h 500 --direction northward" width="23.5%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-10-09T21.12.23-eastward-v128,131-x49279..49282y84588..84593-z17-40.712856632074875,-74.01234090253817-600.0x1154.0m.gif" title="python3 googlemapsat88mph.py 40.712856632074875,-74.01234090253817 600 1154 -h 500 --direction eastward" width="23.5%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-10-09T21.14.59-southward-v128,131-x184948..184951y154078..154082-z18-40.741353668424345,-73.9895488363578-300.0x577.0m.gif" title="python3 googlemapsat88mph.py 40.741353668424345,-73.9895488363578 300 577 -h 500 --direction southward" width="23.5%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-10-09T21.16.16-northward-v128,131-x77206..77210y108048..108054-z18-40.76087698160325,-73.97128173930965-400.0x769.0m.gif" title="python3 googlemapsat88mph.py 40.76087698160325,-73.97128173930965 400 769 -w 500 --direction northward" width="23.5%">

Because Google regularly removes the oldest available versions, all of this is rather ephemeral – a year from now (which, at the time of writing, was July 2021), the invocations of this tool that have created the GIFs above may yield totally different results. Longer-term timelapses of the surface of our planet can be found on [Google Earth Timelapse](https://earthengine.google.com/timelapse/) *(or through [@earthacrosstime](https://twitter.com/earthacrosstime), another weekend project of mine, namely a Twitter bot that posts randomly selected timelapses off it)*, but what's available there doesn't reach the high resolution of Google Maps (and isn't available for 45-degree views).


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

That'll wax poetic about the available command-line flags and arguments. Importantly, there are three positional arguments, *i.e.*, you've got to set these:

1. The latitude-longitude pair you're interested in, along with
2. how wide (east-west extent) and...
3. ...how tall (north-south extent, both in meters) the downloaded area should be.

Along with those three, you need to supply a value for at least one of the `-m`, `-w`, and `-h` flags – the `--help` output explains them in detail.

For example, the following invocation will create the first of the GIFs embedded above, showing the White House:

```bash
$ python3 googlemapsat88mph.py 38.900068,-77.036555 1000 1000 -w 500
```

That's basically it! For your viewing pleasure, here's a video of the CLI in action *(slightly outdated; the `-d` flag for 45-degree imagery has been added since)*, first scrolling through the `--help` output, then executing the command from above:

https://user-images.githubusercontent.com/1944410/126881010-a007e632-2229-440b-a0fe-768f5ce22d14.mp4


## FAQ

### Why the name?

Because [when this baby hits 88 miles per hour, you're gonna see some serious shit](https://en.wikipedia.org/wiki/Back_to_the_Future).

### Why did you make this tool?

I became aware of how Google Maps versions its imagery as a side-effect of building and maintaining [ærialbot](https://github.com/doersino/aerialbot). Figuring out a way to explore past imagery seemed super interesting – note that initially, I wasn't sure how far back the available imagery would go. Finding out that it's only about a year was a bit of a letdown, but there's still some gems to be found either way. The ephemerality aspect also appeals to me.

### Does this violate Google's terms of use?

Probably. I haven't checked. But they haven't banned my IP for downloading tens of thousands of map tiles during development and testing (of [ærialbot](https://github.com/doersino/aerialbot) *and* this), so you're probably good as long as you don't use this tool for downloading a centimeter-scale map of your country. What's more, I can't think of a way in which this tool competes with or keeps revenue from any of Google's products. (And it's always worth keeping in mind that Google is an incredibly profitable company that earns the bulk of its income via folks like you just going about their days surfing the ad-filled web.)

### Something is broken – can you fix it?

Possibly. Please feel free to [file an issue](https://github.com/doersino/google-maps-at-88-mph/issues) – I'll be sure to take a look!

<img src="demo/googlemapsat88mph-2021-07-25T14.06.43-v888,891,900,904-x32678..32689y21801..21805-z16-51.471279,-0.464004-4000.0x1280.0m.gif" title="python3 googlemapsat88mph.py 51.471279,-0.464004 4000 1280 -h 500" width="100%">
