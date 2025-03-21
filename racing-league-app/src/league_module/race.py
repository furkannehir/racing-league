from datetime import datetime, timezone
import uuid
class Race:
    def __init__(self, track, date, _id, status="Upcoming"):
        self._id = _id
        self.track = track
        self.date = date
        self.status = status

    def serialize(self):
        return {
            "_id": self._id,
            "track": self.track,
            "date": self.date,
            "status": self.status
        }

    @staticmethod
    def deserialize(data):
        if isinstance(data, str):
            # Handle legacy string format
            return Race(track=data, date=datetime.now(timezone.utc), _id=str(uuid.uuid4()))

        track = data.get("track")
        date_str = data.get("date")
        _id = data.get("_id", uuid.uuid4().hex)
        status = data.get("status", "Upcoming")

        # try:
        #     # Convert to offset-aware datetime
        #     if '+' in date_str:
        #         # Format with timezone offset like +00:00
        #         date_obj = datetime.fromisoformat(date_str)
        #     elif 'Z' in date_str:
        #         # Format with Z for UTC
        #         date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        #     else:
        #         # No timezone info, assume UTC
        #         date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        #         date_obj = date_obj.replace(tzinfo=timezone.utc)
        # except (ValueError, TypeError, AttributeError):
        #     date_obj = datetime.now(timezone.utc)

        return Race(track=track, date=date_str, _id=_id, status=status)