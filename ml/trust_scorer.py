from datetime import datetime


class SourceTrustScorer:
    """
    Source Trust Scoring Engine.
    Assigns a transparent, explainable trust score (0 to 100) and trust level to weather reports
    based on source provenance, verification evidence, duplicate confirmation, and report completeness.
    
    Academic / Hackathon Prototype Disclaimer:
    This scoring system represents an experimental heuristic evaluation and is NOT an official credibility judgment.
    """

    BASE_SCORES = {
        "Official Weather API": 95.0,
        "OpenWeatherMap API": 95.0,
        "Government/Official Source": 95.0,
        "Verified Organization": 85.0,
        "News Website": 75.0,
        "Citizen Report": 50.0,
        "Mastodon": 45.0,
        "Mastodon (Public Feed)": 45.0,
        "Social Media": 35.0,
        "Unknown Source": 25.0
    }

    @classmethod
    def get_base_score(cls, source_name):
        """Get initial base trust score for a given source type."""
        if not source_name:
            return 25.0
        src = str(source_name).strip()
        if src in cls.BASE_SCORES:
            return cls.BASE_SCORES[src]
        for key, val in cls.BASE_SCORES.items():
            if key.lower() in src.lower():
                return val
        return 25.0

    @classmethod
    def get_trust_level(cls, score):
        """Map numerical score to human-readable trust label."""
        if score >= 80.0:
            return "High Trust"
        elif score >= 50.0:
            return "Medium Trust"
        else:
            return "Low Trust"

    @classmethod
    def calculate_trust(cls, source, verification_result=None, verification_score=None, duplicate_status=None, latitude=None, longitude=None, report_datetime=None, image_url=None):
        """
        Calculate final trust score, level, and human-readable explanation reason.
        
        Formula:
        Final Score = Base Score + Verification Adjustment + Duplicate Adjustment + Completeness Bonus
        (Clamped to 0.0 - 100.0)
        """
        if isinstance(source, dict):
            rep_dict = source
            source = rep_dict.get("source", "Citizen Report")
            if verification_result is None:
                verification_result = rep_dict.get("verification_result")
            if verification_score is None:
                verification_score = rep_dict.get("verification_score")
            if duplicate_status is None:
                duplicate_status = rep_dict.get("duplicate_status")
            if latitude is None:
                latitude = rep_dict.get("latitude")
            if longitude is None:
                longitude = rep_dict.get("longitude")
            if report_datetime is None:
                report_datetime = rep_dict.get("report_datetime")
            if image_url is None:
                image_url = rep_dict.get("image_url")

        updated_at = datetime.now()
        base = cls.get_base_score(source)
        score = base
        reasons = []

        reasons.append(f"Received base trust score of {base:.0f} for source '{source or 'Unknown'}'.")

        # 1. Verification Evidence Adjustment
        v_res = str(verification_result or "").strip()
        v_score = float(verification_score) if verification_score is not None else None

        if v_res == "Likely Consistent" or (v_score is not None and v_score >= 70.0):
            bonus = 20.0 if v_score is None else (v_score / 100.0) * 25.0
            score += bonus
            reasons.append(f"Verification analysis found report consistent with observation data (+{bonus:.1f} pts).")
        elif v_res == "Suspicious" or (v_score is not None and v_score < 40.0):
            penalty = 30.0
            score -= penalty
            reasons.append(f"Verification analysis detected contradiction with observation data (-{penalty:.1f} pts).")
        elif v_res == "Needs Verification":
            reasons.append("Verification status is unconfirmed (0 pts).")

        # 2. Duplicate / Crowd Confirmation Adjustment
        dup_stat = str(duplicate_status or "").strip()
        if dup_stat in ["Potential Duplicate", "Related Report"]:
            bonus = 10.0
            score += bonus
            reasons.append(f"Corroborated by related citizen ground reports (+{bonus:.1f} pts).")

        # 3. Report Completeness Bonus
        completeness_bonus = 0.0
        if latitude is not None and longitude is not None:
            completeness_bonus += 5.0
        if report_datetime:
            completeness_bonus += 5.0
        if image_url and str(image_url).strip():
            completeness_bonus += 5.0

        if completeness_bonus > 0:
            score += completeness_bonus
            reasons.append(f"Received completeness bonus for location/media details (+{completeness_bonus:.1f} pts).")

        final_score = round(max(0.0, min(100.0, score)), 2)
        trust_level = cls.get_trust_level(final_score)
        explanation = " ".join(reasons)

        return final_score, trust_level, explanation, updated_at
