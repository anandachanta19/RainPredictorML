import pickle
import numpy as np
import requests
import logging
from django.shortcuts import render
from geopy.geocoders import Nominatim
from .forms import LocationForm
import requests
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Load model with better error handling
try:
    with open("rainPredictor/rf_model.pkl", "rb") as f:
        model = pickle.load(f)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    model = None

def fetch_weather_data(lat, lon):
    current_date = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Fetching weather data for lat={lat}, lon={lon}, date={current_date}")

    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "relative_humidity_2m,apparent_temperature,precipitation,rain,surface_pressure,cloud_cover",
        "timezone": "auto",
        "forecast_days": 1
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        data = response.json()
        logger.debug(f"API response: {data}")

        if "hourly" not in data:
            logger.error("No hourly data in API response")
            return None, None

        hourly_data = data["hourly"]
        try:
            time_9am = f"{current_date}T09:00"
            time_3pm = f"{current_date}T15:00"

            index_9am = hourly_data["time"].index(time_9am)
            index_3pm = hourly_data["time"].index(time_3pm)
        except ValueError as e:
            logger.error(f"Time index error: {e}, available times: {hourly_data['time']}")
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
        logger.info(f"Weather data retrieved successfully: 9am={data_9am}, 3pm={data_3pm}")
        return data_9am, data_3pm
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error in fetch_weather_data: {e}")
        return None, None

def preprocess_data(lat, lon):
    data_9am, data_3pm = fetch_weather_data(lat, lon)
    if data_9am is None or data_3pm is None:
        logger.error("Missing weather data, cannot preprocess")
        return None

    try:
        feature_array = np.array([[data_9am["humidity"], data_3pm["humidity"],
                               data_9am["pressure"], data_3pm["pressure"],
                               data_9am["cloud_cover"], data_3pm["cloud_cover"],
                               data_9am["temperature"], data_3pm["temperature"]]])
        logger.info(f"Preprocessed feature array: {feature_array}")
        return feature_array
    except Exception as e:
        logger.error(f"Error in preprocess_data: {e}")
        return None

def get_lat_lon(location_name):
    logger.info(f"Getting coordinates for location: {location_name}")
    try:
        geolocator = Nominatim(user_agent="rain_predictor_django")
        location = geolocator.geocode(location_name)
        if location:
            logger.info(f"Location found: {location.latitude}, {location.longitude}")
            return (location.latitude, location.longitude)
        else:
            logger.error(f"Location not found: {location_name}")
            return (None, None)
    except Exception as e:
        logger.error(f"Error in get_lat_lon: {e}")
        return (None, None)

def predict_rain(request):
    result = None
    location_name = None
    error = None
    
    if request.method == "POST":
        logger.info(f"Processing POST request: {request.POST}")
        form = LocationForm(request.POST)
        if form.is_valid():
            location_name = form.cleaned_data["location"]
            logger.info(f"Form is valid, location: {location_name}")
            
            lat, lon = get_lat_lon(location_name)
            if lat is None or lon is None:
                error = f"Could not find coordinates for location: {location_name}"
                logger.error(error)
            else:
                features = preprocess_data(lat, lon)
                if features is None:
                    error = f"Could not fetch weather data for {location_name}"
                    logger.error(error)
                elif model is None:
                    error = "Prediction model is not available"
                    logger.error(error)
                else:
                    try:
                        prediction = model.predict(features)
                        result = "Yes" if prediction[0] == 1 else "No"
                        logger.info(f"Prediction for {location_name}: {result}")
                    except Exception as e:
                        error = f"Error making prediction: {str(e)}"
                        logger.error(f"Prediction error: {e}")
        else:
            logger.error(f"Form is invalid: {form.errors}")
    else:
        form = LocationForm()
        logger.info("GET request, rendering empty form")

    context = {
        "form": form, 
        "result": result, 
        "location_name": location_name,
        "error": error
    }
    return render(request, "rainPredictor/predict.html", context)
