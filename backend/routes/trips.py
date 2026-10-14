from flask import Blueprint, jsonify, request

from database import get_db
from models import (
    TRIP_STATUSES,
    count_activities_outside_dates,
    find_trip,
    trip_to_dict,
)
from validation import parse_id, validate_trip

bp = Blueprint("trips", __name__, url_prefix="/api/trips")


@bp.get("")
def list_trips():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().lower()
    if status and status not in TRIP_STATUSES:
        return jsonify(error=f"Status must be one of: {', '.join(TRIP_STATUSES)}"), 400

    query = "SELECT * FROM trips"
    params = []
    if search:
        query += " WHERE name LIKE ? ESCAPE '\\' OR destination LIKE ? ESCAPE '\\'"
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params = [f"%{escaped}%", f"%{escaped}%"]
    query += " ORDER BY start_date, id"

    rows = get_db().execute(query, params).fetchall()
    trips = [trip_to_dict(row) for row in rows]
    if status:
        trips = [trip for trip in trips if trip["status"] == status]
    return jsonify(trips)


@bp.post("")
def create_trip():
    trip, error = validate_trip(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    db = get_db()
    cursor = db.execute(
        """INSERT INTO trips (name, destination, start_date, end_date, budget, description)
           VALUES (:name, :destination, :start_date, :end_date, :budget, :description)""",
        trip,
    )
    db.commit()
    return jsonify(trip_to_dict(find_trip(cursor.lastrowid))), 201


@bp.get("/<trip_id>")
def get_trip(trip_id):
    trip_id = parse_id(trip_id)
    if trip_id is None:
        return jsonify(error="Invalid trip id"), 400
    row = find_trip(trip_id)
    if row is None:
        return jsonify(error="Trip not found"), 404
    return jsonify(trip_to_dict(row))


@bp.put("/<trip_id>")
def update_trip(trip_id):
    trip_id = parse_id(trip_id)
    if trip_id is None:
        return jsonify(error="Invalid trip id"), 400
    if find_trip(trip_id) is None:
        return jsonify(error="Trip not found"), 404

    trip, error = validate_trip(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    if count_activities_outside_dates(trip_id, trip["start_date"], trip["end_date"]) > 0:
        return jsonify(error="Some activities fall outside the new trip dates. Edit or delete them first"), 400

    db = get_db()

    db.execute(
        """UPDATE trips SET name = :name, destination = :destination, start_date = :start_date,
           end_date = :end_date, budget = :budget, description = :description
           WHERE id = :id""",
        {**trip, "id": trip_id},
    )
    db.commit()
    return jsonify(trip_to_dict(find_trip(trip_id)))


@bp.delete("/<trip_id>")
def delete_trip(trip_id):
    trip_id = parse_id(trip_id)
    if trip_id is None:
        return jsonify(error="Invalid trip id"), 400
    if find_trip(trip_id) is None:
        return jsonify(error="Trip not found"), 404

    db = get_db()
    db.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    db.commit()
    return jsonify(message="Trip deleted")
