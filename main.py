import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from rapidfuzz import process, fuzz
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo



# ============================================================
# GET YESTERDAY'S MATCH RESULTS
# ============================================================
def ResultsMatches():

    html = requests.get(
        "https://www.livescore.cz/?d=-1",
        timeout=30
    )

    html.raise_for_status()

    soup = BeautifulSoup(
        html.text,
        "html.parser"
    )


    for tag in soup.find_all(
        ["h4", "span"]
    ):
        tag.decompose()


    matches = []

    for a in soup.select(
        "a.fin, a.sched, a.live"
    ):

        parts_text = []
        sib = a.previous_sibling

        while sib is not None:
            if getattr(sib, "name", None) in ("br", "a"):
                break
            if isinstance(sib, str):
                parts_text.append(sib)
            sib = sib.previous_sibling

        teams = "".join(reversed(parts_text)).strip()

        if " - " not in teams:
            continue

        home_team, away_team = teams.split(
            " - ",
            1
        )

        href = a.get(
            "href",
            ""
        )

        parts = href.split("/")

        match_id = (
            parts[2]
            if len(parts) > 2
            else None
        )

        matches.append({
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "result": a.get_text(
                strip=True
            )
        })


    uganda_now = datetime.now(
        ZoneInfo("Africa/Kampala")
    )



    yesterday = (
        uganda_now
        - timedelta(days=1)
    )

    date = yesterday.strftime(
        "%a_%d_%b"
    )
    return matches, date





def updateMatchesResults():

    # ============================================================
    # PROCESS BET RESULT
    # ============================================================

    def processResults(result, prediction):

        try:
            homeGoals, awayGoals = map(
                int,
                result.split("-")
            )
        except Exception:
            return "lost"

        totalGoals = homeGoals + awayGoals
        pred = prediction.strip().lower()

        # --------------------------------------------------------
        # Markets handled separately
        # --------------------------------------------------------

        if any(
            x.lower() in pred
            for x in [
                "corners",
                "corner",
                "cards",
                "/",
                "ht/ft"
            ]
        ):
            return "link"

        # --------------------------------------------------------
        # Handicap
        # --------------------------------------------------------

        if (
            ("h" in pred or "a" in pred)
            and ("+" in pred or "-" in pred)
        ):
            return "link"

        # --------------------------------------------------------
        # Correct score
        # --------------------------------------------------------

        if result.strip() == prediction.strip():
            return "won"

        # --------------------------------------------------------
        # Draw
        # --------------------------------------------------------

        if homeGoals == awayGoals:

            if pred in [
                "x",
                "1x",
                "x2",
                "2x",
                "under or 1x",
                "under or x2",
                "over or 1x",
                "over or x2",
            ]:
                return "won"

        # --------------------------------------------------------
        # Home win
        # --------------------------------------------------------

        elif homeGoals > awayGoals:

            if pred in [
                "1",
                "1x",
                "12",
                "under or 1x",
                "over or 1x",
                "under or 12",
                "over or 12",
            ]:
                return "won"

        # --------------------------------------------------------
        # Away win
        # --------------------------------------------------------

        elif awayGoals > homeGoals:

            if pred in [
                "2",
                "x2",
                "2x",
                "12",
                "under or x2",
                "over or x2",
                "under or 12",
                "over or 12",
            ]:
                return "won"

        # --------------------------------------------------------
        # Over 2.5
        # --------------------------------------------------------

        if totalGoals > 2:

            if pred in [
                "over",
                "over or 1x",
                "over or x2",
                "over or 12",
            ]:
                return "won"

        # --------------------------------------------------------
        # Under 2.5
        # --------------------------------------------------------

        if totalGoals < 3:

            if pred in [
                "under",
                "under or 1x",
                "under or x2",
                "under or 12",
            ]:
                return "won"

        # --------------------------------------------------------
        # BTTS Yes
        # --------------------------------------------------------

        if homeGoals > 0 and awayGoals > 0:

            if pred in [
                "yes",
                "yes btts",
            ]:
                return "won"

        # --------------------------------------------------------
        # BTTS No
        # --------------------------------------------------------

        if homeGoals == 0 or awayGoals == 0:

            if pred in [
                "no",
                "no btts",
            ]:
                return "won"

        return "lost"

    # ============================================================
    # INITIALIZE FIREBASE
    # ============================================================

    if not firebase_admin._apps:

        cred = credentials.Certificate(
            "privatekey.json"
        )

        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # ============================================================
    # GET YESTERDAY'S MATCH RESULTS
    #
    # ResultsMatches() returns:
    #
    # matches_json
    # date_id
    #
    # Example:
    #
    # date_id = "Sat_15_Aug"
    #
    # matches_json = [
    #     {
    #         "match_id": "...",
    #         "home_team": "...",
    #         "away_team": "...",
    #         "result": "2-1"
    #     }
    # ]
    # ============================================================

    matches_json, date_id = ResultsMatches()

    if not matches_json:
        return

    # ============================================================
    # GET FIREBASE DATE DOCUMENT
    # ============================================================

    date_ref = (
        db
        .collection("bet_matches")
        .document(date_id)
    )

    date_snapshot = date_ref.get()

    if not date_snapshot.exists:
        return

    # ============================================================
    # PREPARE MATCH SEARCH CHOICES
    # ============================================================

    choices = []

    for item in matches_json:

        home = str(
            item.get(
                "home_team",
                ""
            )
        ).strip().lower()

        away = str(
            item.get(
                "away_team",
                ""
            )
        ).strip().lower()

        if not home or not away:
            continue

        choices.append(
            f"{home} vs {away}"
        )

    if not choices:
        return

    # ============================================================
    # FIND ALL PENDING MATCHES
    # ============================================================

    pending_matches = []

    for match_collection in date_ref.collections():

        try:

            query = (
                match_collection
                .where(
                    filter=FieldFilter(
                        "status",
                        "==",
                        "pending"
                    )
                )
                .stream()
            )

            for match in query:

                data = match.to_dict()

                pending_matches.append({

                    "date_id": date_id,

                    "match_collection":
                        match_collection.id,

                    "slip_id":
                        match.id,

                    "prediction":
                        data.get(
                            "prediction",
                            ""
                        ),

                    "homeTeam":
                        data.get(
                            "homeTeam",
                            ""
                        ),

                    "awayTeam":
                        data.get(
                            "awayTeam",
                            ""
                        ),

                    "match_ref":
                        match.reference,
                })

        except Exception as e:

            print(
                f"Failed reading collection "
                f"{match_collection.id}: {e}"
            )

    # ============================================================
    # NO PENDING MATCHES
    # ============================================================

    if not pending_matches:
        return

    # ============================================================
    # CACHE MATCH LOOKUPS
    # ============================================================

    fixture_cache = {}

    # ============================================================
    # FIRESTORE BATCH
    # ============================================================

    batch = db.batch()
    batch_count = 0

    # ============================================================
    # TRACK SLIPS
    # ============================================================

    touched_slips = set()

    # ============================================================
    # PROCESS PENDING MATCHES
    # ============================================================

    for slip in pending_matches:

        try:

            fixture = slip[  "match_collection"]

            home_team = str( slip["homeTeam"] ).strip()

            away_team = str(slip["awayTeam"]).strip()

            prediction = str(slip["prediction"]  ).strip()

            # ----------------------------------------------------
            # CACHE KEY
            # ----------------------------------------------------

            cache_key = (
                date_id,
                fixture,
                home_team.lower(),
                away_team.lower()
            )

            # ----------------------------------------------------
            # FIND MATCH
            # ----------------------------------------------------

            if cache_key in fixture_cache:

                github_match = fixture_cache[
                    cache_key
                ]

            else:

                search_name = (
                    f"{home_team} vs {away_team}"
                )

                normalized_search = (
                    search_name
                    .strip()
                    .lower()
                )

                github_match = None

                # ------------------------------------------------
                # EXACT MATCH
                # ------------------------------------------------

                for index, choice in enumerate(
                    choices
                ):

                    if choice == normalized_search:

                        github_match = (
                            matches_json[index]
                        )

                        break

                # ------------------------------------------------
                # FUZZY MATCH
                # ------------------------------------------------

                if github_match is None:

                    result = process.extractOne(
                        normalized_search,
                        choices,
                        scorer=fuzz.token_sort_ratio,
                        score_cutoff=65
                    )

                    if result is None:

                        continue

                    matched_name, score, index = result

                    github_match = (
                        matches_json[index]
                    )

                    print(
                        f"Fuzzy match: "
                        f"{home_team} vs "
                        f"{away_team} "
                        f"→ {matched_name} "
                        f"({score:.1f}%)"
                    )

                # ------------------------------------------------
                # CACHE
                # ------------------------------------------------

                fixture_cache[
                    cache_key
                ] = github_match

            # ====================================================
            # GET RESULT
            # ====================================================

            final_result = str(
                github_match.get(
                    "result",
                    ""
                )
            ).strip()

            if not final_result:

                continue

            # ====================================================
            # CALCULATE STATUS
            # ====================================================

            status = processResults(
                final_result,
                prediction
            )

            print(
                f"{home_team} vs "
                f"{away_team} → "
                f"{final_result} → "
                f"{status}"
            )

            # ====================================================
            # UPDATE bet_matches DOCUMENT
            # ====================================================

            bet_match_ref = slip[
                "match_ref"
            ]

            batch.update(
                bet_match_ref,
                {
                    "ft_results":
                        final_result,

                    "status":
                        status,

                    "match_id":
                        github_match.get(
                            "match_id",
                            ""
                        ),
                }
            )

            batch_count += 1

            # ====================================================
            # UPDATE SLIP
            # ====================================================

            slip_ref = (
                db
                .collection("slips")
                .document(
                    slip["slip_id"]
                )
            )

            slip_update = {

                f"matches.{fixture}.status":
                    status,

                f"matches.{fixture}.match_id":
                    (
                        github_match.get(
                            "match_id",
                            ""
                        )
                        if status == "link"
                        else ""
                    ),

                f"matches.{fixture}.fullTime":
                    final_result,
            }

            # ----------------------------------------------------
            # If any match loses, slip loses
            # ----------------------------------------------------

            if status == "lost":

                slip_update[
                    "status"
                ] = "lost"

            batch.update(
                slip_ref,
                slip_update
            )

            batch_count += 1

            # ----------------------------------------------------
            # Remember touched slip
            # ----------------------------------------------------

            touched_slips.add(
                slip["slip_id"]
            )

            # ====================================================
            # FIRESTORE BATCH LIMIT
            # ====================================================

            if batch_count >= 450:

                batch.commit()

                batch = db.batch()

                batch_count = 0

        except Exception as e:

            print(
                f"Failed processing "
                f"{slip.get('homeTeam', '')} vs "
                f"{slip.get('awayTeam', '')}: "
                f"{e}"
            )

    # ============================================================
    # COMMIT REMAINING MATCH UPDATES
    # ============================================================

    if batch_count > 0:

        batch.commit()

    # ============================================================
    # SETTLE SLIPS
    # ============================================================

    batch = db.batch()
    batch_count = 0

    for slip_id in touched_slips:

        try:

            slip_ref = (
                db
                .collection("slips")
                .document(slip_id)
            )

            slip_snap = slip_ref.get()

            if not slip_snap.exists:

                continue

            data = slip_snap.to_dict()

            total_matches = int(
                data.get(
                    "totalMatches",
                    0
                )
            )

            matches = data.get(
                "matches",
                {}
            )

            # ----------------------------------------------------
            # Count settled matches
            # ----------------------------------------------------

            settled_matches = 0

            statuses = []

            for match_data in matches.values():

                if not isinstance(
                    match_data,
                    dict
                ):
                    continue

                match_status = match_data.get(
                    "status",
                    ""
                )

                statuses.append(
                    match_status
                )

                if match_status in [
                    "won",
                    "lost",
                    "link"
                ]:

                    settled_matches += 1

            # ----------------------------------------------------
            # Update settled matches
            # ----------------------------------------------------

            update_data = {

                "settledMatches":
                    settled_matches
            }

            # ----------------------------------------------------
            # Finalize slip
            # ----------------------------------------------------

            if (
                total_matches > 0
                and settled_matches >= total_matches
            ):

                if "lost" in statuses:

                    final_status = "lost"

                elif "link" in statuses:

                    final_status = "down"

                else:

                    final_status = "won"

                update_data[
                    "status"
                ] = final_status

                # print(
                #     f"Slip {slip_id} → "
                #     f"{final_status}"
                # )

            batch.update(
                slip_ref,
                update_data
            )

            batch_count += 1

            # ----------------------------------------------------
            # Batch limit
            # ----------------------------------------------------

            if batch_count >= 450:

                batch.commit()

                batch = db.batch()

                batch_count = 0

        except Exception as e:

            print(
                f"Failed updating slip "
                f"{slip_id}: {e}"
            )

    # ============================================================
    # FINAL SLIP COMMIT
    # ============================================================

    if batch_count > 0:

        batch.commit()

    # print(
    #     f"Finished processing {date_id}"
    # )


updateMatchesResults()
