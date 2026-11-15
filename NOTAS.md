# Project notes (decisions so far)

- Focus: Amazon basin only. No Montes Claros data. No Detective mode.
- Tabs: Overview, Investigate, Compare (was "Compare regions"), Map, Learn.
- Map tab: map is the main element. Amazon spots first; custom pin (coordinates) on request. Live data: NASA POWER.
- Keep the interface light: show verdict, 3 numbers and one chart; everything else under "Go deeper" (nothing discarded).
- Audience: 15-25 years old. Friendly wording, no jargon on the main screen.
- No emojis in text. Custom pins only for selections (and variable cards). Pins live in `assets/pins`, mapped in `icons.py`.
  Pins delivered: Evapotranspiration, Soil moisture, Air temperature, Organic carbon aerosol (smoke), Precipitation.
  Added later: humidity, sunlight, wind. Missing (text tile shown instead): black carbon, dust, total aerosol, clouds.
- Logo: `assets/logo.png` (header + favicon). Header panel is light so the dark-green logo is visible.
- Statistics: 95% fixed, CI widened by the autocorrelation factor, period-sensitivity warning, season filter.
- Interface language: English.
- Layout (whiteboard sketches): compact banner with the logo ("reduzir"), vine divider, mostly green site, and a central
  "What would you like to know?" search box right under the banner (type a question, get cards + full analysis).
- Compare: one row of pins where exactly two are picked (A and B); a third click replaces the older choice.
- Map > My own spot: typed coordinates + quick picks (click-to-select was tried and removed).
- Pins: humidity = water drop (was evapotranspiration), evapotranspiration = vapour over water, sunlight = sun, wind = waves.
- Not done yet (sketch ideas to confirm): country selector "Brazil", "Hydro / Forestation" list, "proporcionalidade" tree,
  "Mistery" house. Site name in the sketch: "The Trends of Amazon".
- Sidebar lists every loaded dataset (name, region, years, file).
- Pending: more interface references from the team; NASA POWER live test; confirm `watersheds/shp_8` = Amazon basin.

## Final adjustments (round 3)
- Banner text centred and merged with the question box in one bordered card (banner + vine + search).
- Compare uses only Amazon-basin data (no Manaus / map spots). Map spots stay in the Map tab.
- Map > Amazon spots: nothing preselected, no request until a dot is clicked.
- Map > My own spot: always shows a clickable map. With `streamlit-folium`: click anywhere in the world.
  Without it: clickable 1-degree dot grid over South America. Typed coordinates under "Or type coordinates".
- `iniciar.bat` installs the packages and starts the app (double click).

- Round 4: removed click-to-select from My own spot (folium, grid map). Only typed coordinates + quick picks remain.
- Round 5: the question box no longer accepts typed text; only the pre-written questions (pills) are available.
