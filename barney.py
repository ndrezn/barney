import re
import json
from statistics import mean
from urllib.request import urlopen
import os

import gspread
import plotly.express as px
import pandas as pd

gc = gspread.service_account()


url = os.getenv("SHEETS_URL")
# Read in the dataset from Google Sheets
workbook = gc.open_by_url(url)
sheet = workbook.worksheet("Form Responses 1")
data = sheet.get_all_values()

# Convert to Pandas
df = pd.DataFrame(data)

# Load in the handy-dandy zip-to-fips matcher file
with urlopen(
    "https://raw.githubusercontent.com/bgruber/zip2fips/master/zip2fips.json"
) as response:
    zip_to_fips = json.load(response)

# Load in our FIPS geojson file
with urlopen(
    "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
) as response:
    counties = json.load(response)

# Reshape the dataset
df.columns = df.iloc[3]
df = df[4:]
df = df.reset_index(drop=True)
df = df.rename(
    columns={
        "What was your childhood zip code (if there are multiple, choose the one from when you were in your peak Barney-hating age)": "zip",
        "If you're not from the US, what country are you from?": "country",
        "If you sang anti-Barney songs, what was the age when your Barney hate peaked?": "peak_hate",
        "What year were you born? ": "birth_year",
    }
)

# Helper function to convert cells with one int into an int
def int_fixer(item):
    i = re.search(r"\d+", item)
    return i.group() if i else None


# Mean several ints in a cell into just one
def age_fixer(year):
    ints = list(map(int, re.findall(r"\d+", year)))
    return int(mean(ints)) if ints else None


# Given a zip code, return its corresponding fips using the key
def get_fips(zip_code):
    try:
        zip_code = str(zip_code).zfill(5) if zip_code else None
        return zip_to_fips[zip_code]
    except KeyError:
        return None


# Clean the data using our helper functions
df["zip"] = df["zip"].apply(lambda zip: int_fixer(zip))
df["birth_year"] = df["birth_year"].apply(
    lambda zip: int(int_fixer(zip)) if int_fixer(zip) else None
)

df["peak_hate"] = df["peak_hate"].apply(lambda year: age_fixer(year))
df = df.dropna(subset=["birth_year", "peak_hate"])

# New column with the year ppl hated Barney the most
df["hate_year"] = df["birth_year"] + df["peak_hate"]
df = df[df["hate_year"] > 1992]
df = df[df["hate_year"] < 2020]
# Count column. Useful for histograms.
df["count"] = 1
# Fips column with the fips code for each cell.
df["fips"] = df["zip"].apply(lambda zip: get_fips(zip))


# Histogram showing the years people hated barney the most
fig = px.histogram(
    df,
    x="hate_year",
    y="count",
    color="birth_year",
    labels={
        "hate_year": "What year did your Barney hate peak?",
        "count": "folks who hated Barney that year",
        "birth_year": "Birth Year",
    },
)

# Display the figure!
fig.show()

# Choropleth
fig = px.choropleth_mapbox(
    df,
    geojson=counties,
    locations="fips",
    color="peak_hate",
    color_continuous_scale="Viridis",
    range_color=(0, 12),
    mapbox_style="carto-positron",
    zoom=3,
    center={"lat": 37.0902, "lon": -95.7129},
    opacity=0.5,
)
fig.show()
