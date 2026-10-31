# Data sources

The table is generated from each feed's `FEED` definition: `uv run python -m scripts.sources`.
Data keeps its source's licence; exports carry these terms in `manifest.json`.

| Feed | Section | Source | Key | Poll | Terms |
|---|---|---|---|---|---|
| `aircraft` Aircraft (ADS-B) | air | https://adsb.fi/ | — | 30 s | adsb.fi open data: free, non-commercial use (adsb.fi) |
| `airport_infra` Runways & navaids (OurAirports) | air | https://ourairports.com/ | — | 10080 min | Public domain (OurAirports) |
| `airports` Airports & heliports (OurAirports) | air | https://ourairports.com/ | — | 10080 min | Public domain (OurAirports) |
| `faa_notam` NOTAMs, Indian FIRs (FAA NOTAM API) | air | https://api.faa.gov/s/ | `FAA_NOTAM_KEY` | 15 min | FAA NOTAM API; US Government data, API terms at api.faa.gov |
| `opensky` Aircraft (OpenSky Network) | air | https://opensky-network.org/ | — | 15 min | OpenSky Network: free for non-commercial research use; cite OpenSky (opensky-network.org/about/terms-of-use) |
| `restricted_areas` Prohibited / restricted / danger areas (AAI eAIP ENR 5.1) | air | https://aim-india.aai.aero.in/eaip-india | — | 1440 min | Government of India public page (AAI eAIP); terms not stated |
| `border_posts` Border crossings (Wikidata) | defence | https://www.wikidata.org/wiki/Q757292 | — | 10080 min | Wikidata (CC0) |
| `defence_sites` Defence installations (Wikidata) | defence | https://www.wikidata.org/wiki/Q695850 | — | 10080 min | Wikidata (CC0); publicly documented sites only |
| `commodities_india` Gold, silver, crude | economy | https://ibjarates.com/ | — | 60 min | IBJA public rates page (ibjarates.com; IBJA also sells an official API; no redistribution licence stated, attribute IBJA). Brent via unofficial Yahoo Finance endpoint, personal/non-commercial use |
| `fx_inr` INR exchange rates (ECB) | economy | https://frankfurter.dev/ | — | 60 min | Frankfurter open API (no key), data from ECB euro foreign exchange reference rates, crossed to INR; free reuse with attribution to the ECB. AED derived via its USD peg. Not the official FBIL/RBI INR reference rate |
| `markets_india` Indian markets (indices) | economy | https://finance.yahoo.com/quote/%5EBSESN/ | — | 5 min | Unofficial Yahoo Finance endpoint (query1.finance.yahoo.com, no key); index data © BSE/NSE via Yahoo, personal/non-commercial use per Yahoo terms, may be delayed |
| `cert_in` Cyber advisories (CERT-In) | govt | https://www.cert-in.org.in/ | — | 60 min | CERT-In public advisories (Government of India, MeitY); see cert-in.org.in terms of use |
| `gdelt` News events (GDELT) | govt | https://www.gdeltproject.org/ | — | 15 min | GDELT Project: free and open, unrestricted use with citation of gdeltproject.org |
| `city_weather` City weather (Open-Meteo) | hazards | https://open-meteo.com/ | — | 15 min | Open-Meteo free API, CC BY 4.0 (attribute Open-Meteo); non-commercial use without key |
| `cpcb_aqi` Air quality (CPCB) | hazards | https://data.gov.in/resource/real-time-air-quality-index-various-locations | `DATA_GOV_IN_KEY` | 60 min | Government Open Data License - India (GODL); source CPCB |
| `cwc_rivers` River levels above warning (CWC) | hazards | https://ffs.india-water.gov.in/ | — | 30 min | Central Water Commission, Govt. of India (public flood forecast site; no explicit licence) |
| `firms` Active fires (NASA FIRMS) | hazards | https://firms.modaps.eosdis.nasa.gov/ | `FIRMS_MAP_KEY` | 15 min | NASA FIRMS / LANCE, free and open (cite NASA FIRMS); MAP_KEY required |
| `imd_cyclone` Tropical cyclones (IMD RSMC New Delhi) | hazards | https://rsmcnewdelhi.imd.gov.in/ | — | 30 min | Government of India public page; attribution: India Meteorological Department (IMD), RSMC New Delhi |
| `imd_nowcast` Nowcast by district (IMD) | hazards | https://mausam.imd.gov.in/responsive/districtWiseNowcastGIS.php | — | 10 min | Government of India public page; attribution: India Meteorological Department (IMD) |
| `imd_warnings` Weather warnings by district (IMD) | hazards | https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php | — | 30 min | Government of India public page; attribution: India Meteorological Department (IMD) |
| `incois` Ocean & tsunami alerts (INCOIS) | hazards | https://incois.gov.in/site/services/hwa.jsp | — | 15 min | Government of India public page; attribution: Indian National Centre for Ocean Information Services (INCOIS) |
| `ncs_quakes` Earthquakes (NCS) | hazards | https://riseq.seismo.gov.in/ | — | 5 min | Government of India public page; attribution: National Center for Seismology (NCS), MoES |
| `sachet` Disaster alerts (NDMA SACHET) | hazards | https://sachet.ndma.gov.in/ | — | 2 min | Public domain (feed <copyright>); NDMA / issuing agencies |
| `usgs_quakes` Earthquakes (USGS) | hazards | https://earthquake.usgs.gov/earthquakes/feed/ | — | 2 min | Public domain (USGS) |
| `volcanoes` Volcanoes (Smithsonian GVP weekly) | hazards | https://volcano.si.edu/reports_weekly.cfm | — | 360 min | Smithsonian GVP / USGS Weekly Volcanic Activity Report; free use with citation of the Smithsonian Institution Global Volcanism Program |
| `grid_power` Power grid (MERIT India) | infrastructure | https://meritindia.in/ | — | 5 min | Ministry of Power public dashboard (MERIT); no explicit licence stated, attribute MoP / Grid-India |
| `ioda` Internet outages (IODA) | infrastructure | https://ioda.inetintel.cc.gatech.edu/country/IN | — | 10 min | © Georgia Tech Research Corporation, all rights reserved (API notice); attribute IODA |
| `nuclear` Nuclear sites (Wikidata) | infrastructure | https://www.wikidata.org/wiki/Q134447 | — | 10080 min | Wikidata (CC0) |
| `road_incidents` Road incidents (TomTom) | infrastructure | https://developer.tomtom.com/traffic-api | `TOMTOM_KEY` | 10 min | © TomTom; TomTom API terms (display only, no redistribution/storage beyond caching) |
| `ais` Ships (AIS, aisstream.io) | sea | https://aisstream.io/ | `AISSTREAM_KEY` | stream | aisstream.io free API; data use under aisstream.io terms of service (attribution: aisstream.io) |
| `navarea8` NAVAREA VIII warnings (Indian Navy) | sea | https://hydrobharat.gov.in/navarea-warnings | — | 60 min | Government of India public navigational warnings (National Hydrographic Office); not for navigation |
| `launches` Launches (Launch Library 2) | space | https://thespacedevs.com/llapi | — | 60 min | Launch Library 2 by The Space Devs: free API (rate-limited), data under their terms; images carry their own licences |
| `satellites` Satellites (CelesTrak + SGP4) | space | https://celestrak.org/NORAD/elements/ | — | 1 min | CelesTrak GP/SATCAT: free public data from US Space Force (space-track.org) via CelesTrak; elements fetched at most every 6 h per CelesTrak usage policy |
| `space_weather` Space weather (NOAA SWPC) | space | https://www.swpc.noaa.gov/ | — | 15 min | Public domain (NOAA / US Government work) |

## Looked at, not ingested

| Source | Why |
|---|---|
| PIB press releases (pib.gov.in RSS) | Akamai returns 403 to a declared bot user agent |
| AAI AIM-India NOTAMs | NOTAM lists sit behind an encrypted, signed, reCAPTCHA-gated API; FAA API used instead (key) |
| GSI landslide bulletins (Bhusanket) | map services need a token; district PDFs are stamped “Not for public use” |
| IMD official API (api.imd.gov.in) | needs IP whitelisting; IMD's public GeoServer used instead |
| Grid-India / RLDC grid frequency | no live public source found (stale or empty endpoints); MERIT demand/mix used |
| SACHET CAP polygons | polygon endpoint returns 403; alerts placed at district centroids |
| adsb.lol tile sweeps | rate-limited; adsb.fi + OpenSky used |
| BSE / NSE / MCX market data | Akamai 403 to a declared bot (NSE doesn't answer); Yahoo Finance's unofficial spark endpoint used |
| PPAC Indian crude basket | monthly, downloads behind a CAPTCHA; Brent via Yahoo used |
| CWC reservoir storage bulletin | no bulletin since May 2025; the RSMS link is dead |

## Static layers (built once, shipped in `apps/frontend/public/geo/`)

| File | Source | Licence |
|---|---|---|
| india.geojson, mask.geojson | datameet `india-composite` (Survey of India outline) | CC0 |
| districts.geojson, states.geojson | datameet Census 2011 districts, States/Admin2 | CC BY 4.0 |
| borders.geojson, defacto.geojson, neighbours.geojson | India outline + Natural Earth 10m boundaries (lengths: MHA) | public domain |
| maritime.geojson, scope.geojson | Marine Regions (VLIZ) EEZ / 24 nm / 12 nm for India | CC BY 4.0 |
| highways, railways, rivers overlays | OpenStreetMap via the OpenFreeMap basemap tiles | ODbL |

Rebuild with `scripts/build_geo.py`, `scripts/build_borders.py`, `scripts/build_maritime.py` (each docstring lists its inputs).
