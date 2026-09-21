import math
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate geographic distance between two lat/lon coordinates in kilometers using Haversine formula.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        r = 6371.0  # Earth radius in kilometers
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(float(lat1)))
            * math.cos(math.radians(float(lat2)))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c
    except (ValueError, TypeError):
        return None


def calculate_text_similarity(text1, text2):
    """
    Calculate TF-IDF Cosine Similarity between two text strings.
    """
    if not text1 or not text2:
        return 0.0
    t1 = str(text1).strip().lower()
    t2 = str(text2).strip().lower()
    if t1 == t2:
        return 1.0

    try:
        vectorizer = TfidfVectorizer().fit_transform([t1, t2])
        vectors = vectorizer.toarray()
        sim = cosine_similarity([vectors[0]], [vectors[1]])[0][0]
        return float(sim)
    except Exception:
        # Fallback word overlap Jaccard similarity
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0


class DuplicateDetector:
    """
    Multi-Signal Duplicate & Related Weather Report Detection Module.
    Combines:
    1. Text Similarity (TF-IDF + Cosine Similarity)
    2. City & State Matching
    3. Event Type Matching
    4. Timestamp Proximity (24-hour lookback window)
    5. Geographic Proximity (Haversine distance when lat/lon available)
    
    Classification Thresholds:
    - Potential Duplicate : Similarity Score >= 75.0%
    - Related Report     : 45.0% <= Similarity Score < 75.0%
    - Unique             : Similarity Score < 45.0%
    """

    LOOKBACK_HOURS = 24

    @classmethod
    def detect_duplicates(cls, new_report, recent_reports):
        """
        Compare new_report against recent_reports (last 24 hours).
        
        Parameters:
        - new_report (dict): Target report data (city, state, event_type, report_text, latitude, longitude)
        - recent_reports (list of dicts): Preceding citizen reports from database
        
        Returns tuple:
        (is_duplicate: bool, duplicate_group: str, duplicate_status: str, similarity_score: float, reason: str, checked_at: datetime)
        """
        checked_at = datetime.now()
        new_city = str(new_report.get("city", "")).strip().lower()
        new_state = str(new_report.get("state", "")).strip().lower()
        new_event = str(new_report.get("event_type", "")).strip().lower()
        new_text = str(new_report.get("report_text", "")).strip()
        new_lat = new_report.get("latitude")
        new_lon = new_report.get("longitude")

        best_match = None
        highest_score = 0.0
        match_reasons = []

        if recent_reports:
            for existing in recent_reports:
                # Skip self if report exists in list
                if existing.get("id") and new_report.get("id") and existing.get("id") == new_report.get("id"):
                    continue

                ex_city = str(existing.get("city", "")).strip().lower()
                ex_state = str(existing.get("state", "")).strip().lower()
                ex_event = str(existing.get("event_type", "")).strip().lower()
                ex_text = str(existing.get("report_text", "")).strip()
                ex_lat = existing.get("latitude")
                ex_lon = existing.get("longitude")

                # Location check
                same_city = (new_city == ex_city) and bool(new_city)
                same_state = (new_state == ex_state) and bool(new_state)
                if not same_city and not same_state:
                    continue  # Skip comparison if completely different locations

                # Event check
                same_event = (new_event == ex_event) and bool(new_event)

                # Text similarity
                text_sim = calculate_text_similarity(new_text, ex_text)

                # Geo distance
                geo_dist = haversine_distance(new_lat, new_lon, ex_lat, ex_lon)

                # Score calculation
                score = 0.0
                reasons = []

                if same_city:
                    score += 30.0
                    reasons.append(f"Same city ({existing.get('city')}).")
                elif same_state:
                    score += 15.0
                    reasons.append(f"Same state ({existing.get('state')}).")

                if same_event:
                    score += 25.0
                    reasons.append(f"Matching event type ({existing.get('event_type')}).")

                if text_sim > 0.0:
                    score += (text_sim * 35.0)
                    reasons.append(f"Text similarity: {text_sim*100:.1f}%.")

                if geo_dist is not None and geo_dist <= 15.0:
                    score += 10.0
                    reasons.append(f"Geographic proximity: {geo_dist:.1f} km apart.")

                final_score = min(100.0, max(0.0, score))

                if final_score > highest_score:
                    highest_score = final_score
                    best_match = existing
                    match_reasons = reasons

        # Category Determination
        clean_score = round(highest_score, 2)
        city_slug = (new_report.get('city') or 'GENERAL').upper().replace(' ', '')
        event_slug = (new_report.get('event_type') or 'WEATHER').upper().replace(' ', '')
        default_grp = f"GRP-{city_slug}-{event_slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if highest_score >= 75.0 and best_match:
            is_dup = True
            grp = best_match.get("duplicate_group") or default_grp
            status = "Potential Duplicate"
            reason = f"High similarity with Report #{best_match['id']}. " + " ".join(match_reasons)
        elif highest_score >= 45.0 and best_match:
            is_dup = False
            grp = best_match.get("duplicate_group") or default_grp
            status = "Related Report"
            reason = f"Moderate similarity with Report #{best_match['id']}. " + " ".join(match_reasons)
        else:
            is_dup = False
            grp = default_grp
            status = "Unique"
            reason = "No matching citizen report found within 24-hour lookback window."

        return is_dup, grp, status, clean_score, reason, checked_at
