from datetime import datetime


class WeatherEventClassifier:
    """
    Modular Weather Event Classification Module.
    Currently implements a transparent, rule-based prototype approach using environmental thresholds.
    Designed with a clean interface so it can be seamlessly replaced or enhanced with a trained 
    scikit-learn / TensorFlow model in future iterations.
    
    Academic / Hackathon Prototype Disclaimer:
    This classifier provides automated experimental event labelling and is NOT an official weather warning system.
    """

    EVENT_TYPES = [
        "Normal Weather",
        "Heavy Rainfall",
        "Thunderstorm",
        "Heatwave",
        "Fog",
        "Strong Wind",
        "Dust Storm",
        "Flood Risk"
    ]

    @classmethod
    def classify(cls, temperature, humidity, wind_speed, weather_condition="", weather_description=""):
        """
        Classify environmental weather observations into an event category and calculate confidence score.
        
        Threshold Rules (Prototype):
        --------------------------------------------------------------------------------------------------
        1. Thunderstorm:
           - Condition / Description contains 'thunderstorm', 'lightning', 'thunder'
           - Confidence: 95.0%
           
        2. Flood Risk (Potential Flooding Conditions):
           - Condition / Description contains 'extreme rain', 'very heavy rain', 'torrential'
           - OR ('heavy rain' AND (Humidity >= 85% OR Wind Speed >= 8.0 m/s))
           - Confidence: 88.5%
           
        3. Heavy Rainfall:
           - Condition / Description contains 'heavy rain', 'shower rain'
           - OR (Condition == 'Rain' AND Humidity >= 80% AND Wind Speed >= 5.0 m/s)
           - Confidence: 85.0%
           
        4. Dust Storm:
           - Condition / Description contains 'dust', 'sand', 'sandstorm', 'duststorm', 'ash'
           - Confidence: 90.0%
           
        5. Fog:
           - Condition / Description contains 'fog', 'mist', 'haze', 'smoke'
           - Confidence: 90.0%
           
        6. Heatwave:
           - Temperature >= 40.0°C OR (Temperature >= 38.0°C AND Humidity < 30%)
           - Confidence: 86.0% - 98.0%
           
        7. Strong Wind:
           - Wind Speed >= 12.0 m/s OR (Wind Speed >= 8.0 m/s AND text contains 'wind'/'squall'/'gale')
           - Confidence: 80.0% - 96.0%
           
        8. Normal Weather:
           - Default for observations within baseline environmental limits
           - Confidence: 95.0%
        --------------------------------------------------------------------------------------------------
        
        Returns tuple: (event_type: str, event_confidence: float, classified_at: datetime)
        """
        try:
            temp = float(temperature) if temperature is not None else 25.0
        except (ValueError, TypeError):
            temp = 25.0

        try:
            hum = float(humidity) if humidity is not None else 50.0
        except (ValueError, TypeError):
            hum = 50.0

        try:
            wind = float(wind_speed) if wind_speed is not None else 2.0
        except (ValueError, TypeError):
            wind = 2.0

        cond_str = str(weather_condition or "").lower()
        desc_str = str(weather_description or "").lower()
        text_combined = f"{cond_str} {desc_str}"
        classified_at = datetime.now()

        # Rule 1: Thunderstorm
        if any(term in text_combined for term in ["thunderstorm", "lightning", "thunder"]):
            return "Thunderstorm", 95.0, classified_at

        # Rule 2: Flood Risk (Potential Flooding Conditions)
        if any(term in text_combined for term in ["extreme rain", "very heavy rain", "torrential"]) or \
           ("heavy rain" in text_combined and (hum >= 85 or wind >= 8.0)):
            return "Flood Risk", 88.5, classified_at

        # Rule 3: Heavy Rainfall
        if "heavy rain" in text_combined or "shower rain" in text_combined or \
           ("rain" in cond_str and hum >= 80 and wind >= 5.0):
            return "Heavy Rainfall", 85.0, classified_at

        # Rule 4: Dust Storm
        if any(term in text_combined for term in ["dust", "sand", "sandstorm", "duststorm", "ash"]):
            return "Dust Storm", 90.0, classified_at

        # Rule 5: Fog / Mist
        if any(term in text_combined for term in ["fog", "mist", "haze", "smoke"]):
            return "Fog", 90.0, classified_at

        # Rule 6: Heatwave
        if temp >= 40.0:
            confidence = min(98.0, 85.0 + (temp - 40.0) * 2.5)
            return "Heatwave", round(confidence, 2), classified_at
        elif temp >= 38.0 and hum < 30:
            return "Heatwave", 86.0, classified_at

        # Rule 7: Strong Wind
        if wind >= 12.0 or (wind >= 8.0 and any(term in text_combined for term in ["wind", "squall", "gale"])):
            confidence = min(96.0, 80.0 + (wind - 8.0) * 3.0)
            return "Strong Wind", round(confidence, 2), classified_at

        # Rule 8: Default - Normal Weather
        return "Normal Weather", 95.0, classified_at
