import pickle
import numpy as np
import requests
from django.shortcuts import render
from geopy.geocoders import Nominatim
from .forms import LocationForm
import requests
from datetime import datetime

with open("rainPredictor/rf_model.pkl", "rb") as f:
    model = pickle.load(f)

def fetch_weather_data(lat, lon):
    current_date = datetime.now().strftime("%Y-%m-%d")

    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "relative_humidity_2m,apparent_temperature,precipitation,rain,surface_pressure,cloud_cover",
        "timezone": "auto",
        "forecast_days": 1
    }
    response = requests.get(base_url, params=params)
    data = response.json()

    if "hourly" not in data:
        return None, None

    hourly_data = data["hourly"]
    try:
        time_9am = f"{current_date}T09:00"
        time_3pm = f"{current_date}T15:00"

        index_9am = hourly_data["time"].index(time_9am)
        index_3pm = hourly_data["time"].index(time_3pm)
    except ValueError:
        return None, None

    data_9am = {
        "humidity": hourly_data["relative_humidity_2m"][index_9am],
        "temperature": hourly_data["apparent_temperature"][index_9am],
        "pressure": hourly_data["surface_pressure"][index_9am],
        "cloud_cover": hourly_data["cloud_cover"][index_9am],
    }
    data_3pm = {
        "humidity": hourly_data["relative_humidity_2m"][index_3pm],
        "temperature": hourly_data["apparent_temperature"][index_3pm],
        "pressure": hourly_data["surface_pressure"][index_3pm],
        "cloud_cover": hourly_data["cloud_cover"][index_3pm],
    }

    return data_9am, data_3pm

def preprocess_data(lat, lon):
    data_9am, data_3pm = fetch_weather_data(lat, lon)
    if data_9am is None or data_3pm is None:
        return None

    feature_array = np.array([[data_9am["humidity"], data_3pm["humidity"],
                               data_9am["pressure"], data_3pm["pressure"],
                               data_9am["cloud_cover"], data_3pm["cloud_cover"],
                               data_9am["temperature"], data_3pm["temperature"]]])
    return feature_array

def get_lat_lon(location_name):
    geolocator = Nominatim(user_agent="rain_predictor_django")
    location = geolocator.geocode(location_name)
    return (location.latitude, location.longitude) if location else (None, None)

def predict_rain(request):
    result = None
    location_name = None
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            location_name = form.cleaned_data["location"]
            lat, lon = get_lat_lon(location_name)

            if lat is not None and lon is not None:
                features = preprocess_data(lat, lon)
                if features is not None:
                    prediction = model.predict(features)
                    result = "Yes" if prediction[0] == 1 else "No"
    else:
        form = LocationForm()

    return render(request, "rainPredictor/predict.html", {"form": form, "result": result, "location_name": location_name})
