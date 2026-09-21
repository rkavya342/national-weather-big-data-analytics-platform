from datetime import datetime


class ReportVerifier:
    """
    AI-Assisted Weather Report Verification Module.
    Compares citizen-submitted weather reports against recent meteorological observations from api_weather_data.
    Uses a transparent, heuristic scoring mechanism to assess consistency.
    
    Academic / Hackathon Prototype Disclaimer:
    This verification engine provides automated heuristic consistency scoring and is NOT an official fact-checking,
    legal, medical, or emergency verification system.
    """

    RESULTS = ["Likely Consistent", "Needs Verification", "Suspicious"]

    @classmethod
    def verify_report(cls, report_text, event_type, city, report_datetime=None, recent_obs=None):
        """
        Verify a citizen weather report against recent observation data for the same city.
        
        Parameters:
        - report_text (str): Text description of the citizen report
        - event_type (str): Citizen-reported weather event category
        - city (str): Reported city name
        - report_datetime (datetime/str): Datetime of report
        - recent_obs (dict): Latest matching observation record from api_weather_data
        
        Returns tuple:
        (verification_result: str, verification_score: float, verification_reason: str, verified_at: datetime)
        """
        verified_at = datetime.now()

        # Rule: If no matching weather observation exists for the city
        if not recent_obs:
            return (
                "Needs Verification",
                50.00,
                f"No recent weather observation data available for '{city}' in database to perform cross-verification.",
                verified_at
            )

        score = 50.0  # Base neutral consistency score
        city_obs = recent_obs.get("city", city)
        api_cond = str(recent_obs.get("weather_condition", "")).lower()
        api_desc = str(recent_obs.get("weather_description", "")).lower()
        api_event = str(recent_obs.get("event_type", "")).lower()
        
        try:
            temp = float(recent_obs.get("temperature", 25.0) if recent_obs.get("temperature") is not None else 25.0)
        except (ValueError, TypeError):
            temp = 25.0

        try:
            hum = float(recent_obs.get("humidity", 50.0) if recent_obs.get("humidity") is not None else 50.0)
        except (ValueError, TypeError):
            hum = 50.0

        try:
            wind = float(recent_obs.get("wind_speed", 2.0) if recent_obs.get("wind_speed") is not None else 2.0)
        except (ValueError, TypeError):
            wind = 2.0

        rep_event = str(event_type or "").lower()
        rep_text = str(report_text or "").lower()
        reasons = []

        # 1. Event Type & Condition Consistency Logic
        if any(keyword in rep_event for keyword in ["rain", "flood"]) or "waterlog" in rep_text or "downpour" in rep_text:
            if any(term in f"{api_cond} {api_desc} {api_event}" for term in ["rain", "drizzle", "shower", "thunderstorm", "flood"]):
                score += 35.0
                reasons.append(f"Reported rain/flood event matches observation ({recent_obs.get('weather_condition')}).")
            elif hum >= 75.0:
                score += 20.0
                reasons.append(f"Observation indicates high atmospheric humidity ({hum}%).")
            elif "clear" in api_cond and hum < 50.0:
                score -= 30.0
                reasons.append(f"Observation indicates clear skies with low humidity ({hum}%).")

        elif "thunderstorm" in rep_event or "lightning" in rep_text or "thunder" in rep_text:
            if "thunder" in f"{api_cond} {api_desc} {api_event}":
                score += 40.0
                reasons.append(f"Reported thunderstorm matches OpenWeather observation ({recent_obs.get('weather_description')}).")
            elif "rain" in api_cond:
                score += 25.0
                reasons.append("Observation indicates active precipitation associated with thunderstorm activity.")
            elif "clear" in api_cond:
                score -= 25.0
                reasons.append(f"Observation indicates clear skies, making thunderstorm unlikely.")

        elif "heatwave" in rep_event or "heat" in rep_text or "hot" in rep_text:
            if temp >= 38.0:
                score += 40.0
                reasons.append(f"Observed temperature is high ({temp:.1f}°C).")
            elif temp < 25.0:
                score -= 35.0
                reasons.append(f"Observed temperature is cool ({temp:.1f}°C), contradicting heatwave report.")

        elif "fog" in rep_event or "mist" in rep_text or "smog" in rep_text:
            if any(term in f"{api_cond} {api_desc}" for term in ["fog", "mist", "haze", "smoke"]):
                score += 40.0
                reasons.append(f"Observation confirms fog/mist ({recent_obs.get('weather_description')}).")
            elif hum < 40.0:
                score -= 25.0
                reasons.append(f"Observed humidity is low ({hum}%), making fog unlikely.")

        elif "strong wind" in rep_event or "wind" in rep_text or "gale" in rep_text:
            if wind >= 8.0:
                score += 35.0
                reasons.append(f"Observed wind speed is elevated ({wind} m/s).")
            elif wind < 2.5:
                score -= 20.0
                reasons.append(f"Observed wind speed is calm ({wind} m/s).")

        else:
            # Generic text & condition match fallback
            if api_cond in rep_text or api_desc in rep_text:
                score += 25.0
                reasons.append(f"Report description aligns with condition ({recent_obs.get('weather_condition')}).")

        # Clamp final score between 0.0 and 100.0
        final_score = max(0.0, min(100.0, score))

        # Categorize result
        if final_score >= 70.0:
            result_category = "Likely Consistent"
            explanation = f"Reported {event_type} is consistent with the latest weather observation for {city_obs} (Temp: {temp:.1f}°C, Condition: {recent_obs.get('weather_condition')}). " + " ".join(reasons)
        elif final_score >= 40.0:
            result_category = "Needs Verification"
            explanation = f"Reported {event_type} partially aligns with available observation for {city_obs}. " + " ".join(reasons)
        else:
            result_category = "Suspicious"
            explanation = f"Reported {event_type} differs from the latest available weather observation for {city_obs}. " + " ".join(reasons)

        return result_category, round(final_score, 2), explanation, verified_at
