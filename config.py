"""
Gap checklist configuration — edit this file to update audit rules over time.
Each rule defines what triggers/templates must exist and how they should be configured.
"""

# Properties that require door code triggers (non-Airbnb bookings only)
DOOR_CODE_PROPERTIES = ["CMH", "CMHE", "CMHW"]

# Properties that are exempt from security deposit requirement
SECURITY_DEPOSIT_EXEMPT = ["CMH"]

# Channel names considered "Airbnb" for door code trigger exclusion
AIRBNB_CHANNELS = ["airbnb", "airbnb2", "airbnb_api"]

# --- Gap Checklist ---
# Each entry describes a required trigger or configuration.
# The audit engine uses these to compare against live OwnerRez data.

GAP_CHECKLIST = [
    {
        "id": "immediate_booking_email",
        "description": "Immediate email trigger on booking creation for all properties",
        "type": "trigger",
        "event": "booking_created",
        "channel": "all",          # applies to all channels
        "properties": "all",       # applies to all properties
        "medium": "email",
        "timing_offset_hours": 0,  # fires immediately (within 1 hour)
        "required": True,
    },
    {
        "id": "door_code_non_airbnb",
        "description": "Door code trigger for CMH/CMHE/CMHW for non-Airbnb bookings",
        "type": "trigger",
        "event": "booking_created",
        "channel": "not_airbnb",   # exclude Airbnb channels
        "properties": DOOR_CODE_PROPERTIES,
        "medium": "email",         # door code delivered via email or sms
        "timing_offset_hours": 0,
        "required": True,
        "keywords": ["door", "code", "lock", "access"],  # template must contain one of these
    },
    {
        "id": "welcome_30day",
        "description": "30-day welcome trigger fires regardless of payment status",
        "type": "trigger",
        "event": "arrival_based",  # fires relative to arrival date
        "properties": "all",
        "medium": "email",
        "timing_offset_days": -30, # 30 days before arrival
        "ignore_payment_status": True,
        "required": True,
        "keywords": ["welcome", "arrival", "check-in", "checkin"],
    },
    {
        "id": "sms_midstay_day2",
        "description": "SMS mid-stay check-in at day 2 post-arrival",
        "type": "trigger",
        "event": "arrival_based",
        "properties": "all",
        "medium": "sms",
        "timing_offset_days": 2,   # 2 days after arrival
        "required": True,
        "keywords": ["check", "enjoying", "everything", "mid-stay", "midstay", "how"],
    },
    {
        "id": "checkout_thankyou",
        "description": "Checkout thank-you email on departure day",
        "type": "trigger",
        "event": "departure_based",
        "properties": "all",
        "medium": "email",
        "timing_offset_days": 0,   # on departure day
        "required": True,
        "keywords": ["thank", "hope", "stay", "checkout", "check out", "review"],
    },
    {
        "id": "returning_guest_75day",
        "description": "Returning guest re-engagement email at 75 days post-departure",
        "type": "trigger",
        "event": "departure_based",
        "properties": "all",
        "medium": "email",
        "timing_offset_days": 75,  # 75 days after departure
        "required": True,
        "keywords": ["return", "back", "again", "miss", "book", "special", "offer"],
    },
    {
        "id": "door_lock_integration",
        "description": "All properties have door lock integration configured",
        "type": "property_config",
        "check": "door_lock",
        "properties": "all",
        "required": True,
    },
    {
        "id": "security_deposit",
        "description": "Security deposit configured on all non-CMH properties",
        "type": "property_config",
        "check": "security_deposit",
        "properties": "non_exempt",  # all except SECURITY_DEPOSIT_EXEMPT
        "required": True,
    },
]
