from datetime import datetime, timezone
import uuid
class Race:
    def __init__(self, track, date, _id, status="Upcoming"):
        self._id = _id
        self.track = track
        self.date = date
        self.status = status

    def serialize(self):
        # Convert datetime to ISO format string for database storage
        date_value = self.date
        if isinstance(self.date, datetime):
            date_value = self.date.isoformat()
        
        return {
            "_id": self._id,
            "track": self.track,
            "date": date_value,
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

        # Parse date string to timezone-aware datetime object
        try:
            if isinstance(date_str, datetime):
                # If it's already a datetime object, ensure it's timezone-aware
                date_obj = date_str
                if not date_obj.tzinfo:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
            elif isinstance(date_str, str):
                # Convert string to offset-aware datetime
                if '+' in date_str or date_str.endswith('Z'):
                    # Format with timezone info
                    if date_str.endswith('Z'):
                        date_str = date_str.replace('Z', '+00:00')
                    date_obj = datetime.fromisoformat(date_str)
                else:
                    # No timezone info, assume UTC
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                    except ValueError:
                        # Try alternative format
                        date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
            else:
                # Fallback for any other type
                date_obj = datetime.now(timezone.utc)
        except (ValueError, TypeError, AttributeError):
            date_obj = datetime.now(timezone.utc)

        return Race(track=track, date=date_obj, _id=_id, status=status)