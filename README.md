# google-maps-at-88-mph




<!--
| test | test | test |
|---|---|---|
| ![](googlemapsat88mph-2021-07-24T20.48.10-v867,868,904-x10011..10019y6368..6377-z14-37.087214,40.058665-15000.0x15000.0m.gif) | ![](googlemapsat88mph-2021-07-24T20.48.10-v867,868,904-x10011..10019y6368..6377-z14-37.087214,40.058665-15000.0x15000.0m.gif) | ![](googlemapsat88mph-2021-07-24T20.48.10-v867,868,904-x10011..10019y6368..6377-z14-37.087214,40.058665-15000.0x15000.0m.gif) |
-->

<img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%">

<img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%"><img src="demo/spacer.gif" width="2%"><img src="demo/googlemapsat88mph-2021-07-24T21.03.20-v868,869,870,891,904-x18742..18745y25068..25071-z16-38.900068,-77.036555-1000.0x1000.0m.gif" width="32%">


## Usage

### Setup

Being a good [Python 3](https://www.python.org) citizen, this tool integrates with `venv` to avoid dependency hell. Run the following commands to get it installed on your system:

```bash
$ git clone https://github.com/doersino/google-maps-at-88-mph
$ python3 -m venv google-maps-at-88-mph
$ cd google-maps-at-88-mph
$ source bin/activate
$ pip3 install -r requirements.txt
```

(To deactivate the virtual environment, run `deactivate`.)


### Configuration

None! Just command-line options.


### Running

TODO

Once you've set everything up, run:

```bash
$ python3 googlemapsat88mph.py --help
```

That'll tell you about the options. Most important are the three positional arguments:

1. The point you're interested in, along with
2. how wide and...
3. ...how tall the imaged area should be.

For example, the following invocation will 

That's basically it!


TODO
- write readme, promote on twitter (make a bot? nah...), etc.
  explain 88 mph reference
  screencapture of cli output
  example gifs/mp4s: my hood, some place in the us, turkey cpi, something in korea or china
  check how often versions change
examples:
python3 googlemapsat88mph.py 48.471839,8.935646 -w 300 -h 300 --image-width 500 --image-height 500
python3 googlemapsat88mph.py "37.087214, 40.058665" 15000 15000 -m 10




## Future work

TODO take another stab at not having to create new tilegrids in every iteration
