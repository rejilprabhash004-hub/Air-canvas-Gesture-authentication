"""
Gesture classification from MediaPipe hand landmarks.

Landmark indices (MediaPipe Hands, 21 points per hand):
    0  = WRIST
    1-4   = THUMB   (CMC, MCP, IP, TIP)
    5-8   = INDEX   (MCP, PIP, DIP, TIP)
    9-12  = MIDDLE  (MCP, PIP, DIP, TIP)
    13-16 = RING    (MCP, PIP, DIP, TIP)
    17-20 = PINKY   (MCP, PIP, DIP, TIP)

Classification approach: for each of the four non-thumb fingers, a
finger counts as "extended" if its TIP is above (smaller y) its PIP
joint by a margin — a simple, explainable geometric rule well suited
for a viva. The thumb is handled separately since it extends
sideways rather than vertically, using x-displacement relative to
handedness (mirrored frame assumed, per hand_detector.py).

NOTE: MediaPipe's normalized image coordinates have y increasing
DOWNWARD (origin top-left), so "extended upward" means a SMALLER y
value, not larger.
"""

# Landmark index constants for readability
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# Minimum normalized-coordinate margin before we trust a finger's
# extended/curled state — filters out borderline/jittery frames.
Y_MARGIN = 0.02
X_MARGIN = 0.02


def _finger_extended_vertical(landmarks, tip_idx, pip_idx):
    """True if the finger tip is clearly above its PIP joint."""
    return landmarks[tip_idx][1] < landmarks[pip_idx][1] - Y_MARGIN


def _thumb_extended(landmarks, handedness):
    """
    Thumb extends sideways, not vertically, so we compare x-coordinates
    of the tip vs the IP joint. Direction depends on which hand is
    presented (mirrored/selfie view, per hand_detector.py):
      - "Right" hand (as MediaPipe reports it in a mirrored frame):
            extended thumb points further LEFT  -> tip.x < ip.x
      - "Left" hand:
            extended thumb points further RIGHT -> tip.x > ip.x
    If handedness is unavailable for any reason, fall back to a
    handedness-agnostic distance check (less precise but safe).
    """
    tip_x = landmarks[THUMB_TIP][0]
    ip_x = landmarks[THUMB_IP][0]

    if handedness == "Right":
        return tip_x < ip_x - X_MARGIN
    elif handedness == "Left":
        return tip_x > ip_x + X_MARGIN
    else:
        # Fallback: thumb tip far from the pinky-MCP base relative to
        # the IP joint suggests an extended thumb, regardless of side.
        import math
        def dist(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])
        return dist(landmarks[THUMB_TIP], landmarks[PINKY_MCP]) > \
               dist(landmarks[THUMB_IP], landmarks[PINKY_MCP])


def get_finger_states(landmarks, handedness):
    """
    Returns a dict of booleans: {"thumb":.., "index":.., "middle":..,
    "ring":.., "pinky":..} indicating which fingers are extended.
    """
    return {
        "thumb": _thumb_extended(landmarks, handedness),
        "index": _finger_extended_vertical(landmarks, INDEX_TIP, INDEX_PIP),
        "middle": _finger_extended_vertical(landmarks, MIDDLE_TIP, MIDDLE_PIP),
        "ring": _finger_extended_vertical(landmarks, RING_TIP, RING_PIP),
        "pinky": _finger_extended_vertical(landmarks, PINKY_TIP, PINKY_PIP),
    }


def classify_gesture(landmarks, handedness):
    """
    Maps raw landmarks to one of the 5 vocabulary gestures, or None if
    the current hand pose doesn't clearly match any of them (this is
    intentional — an ambiguous pose should not silently register as a
    gesture during authentication).

    Vocabulary (matches Config.VALID_GESTURES):
        INDEX        -> only index finger extended
        TWO_FINGERS  -> index + middle extended, ring + pinky curled
        OPEN_PALM    -> all five fingers extended
        THUMB_UP     -> thumb extended, all other fingers curled,
                        AND thumb tip clearly above the wrist (pointing up)
        FIST         -> no fingers extended
    """
    if landmarks is None:
        return None

    states = get_finger_states(landmarks, handedness)
    thumb, index, middle, ring, pinky = (
        states["thumb"], states["index"], states["middle"],
        states["ring"], states["pinky"],
    )

    # FIST: everything curled
    if not any([thumb, index, middle, ring, pinky]):
        return "FIST"

    # OPEN_PALM: everything extended
    if all([thumb, index, middle, ring, pinky]):
        return "OPEN_PALM"

    # INDEX: only index extended
    if index and not any([thumb, middle, ring, pinky]):
        return "INDEX"

    # TWO_FINGERS: index + middle only
    if index and middle and not any([thumb, ring, pinky]):
        return "TWO_FINGERS"

    # THUMB_UP: only thumb extended, and pointing upward (not sideways
    # like a "thumbs to the side" ambiguous pose)
    if thumb and not any([index, middle, ring, pinky]):
        thumb_tip_y = landmarks[THUMB_TIP][1]
        wrist_y = landmarks[WRIST][1]
        if thumb_tip_y < wrist_y - Y_MARGIN:
            return "THUMB_UP"

    return None  # ambiguous / transitional pose — caller should ignore
