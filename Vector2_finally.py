import math
class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x, self.y = x, y

    def clone(self) -> "Vec2":
        return Vec2(self.x, self.y)

    def set(self, v: "Vec2") -> "Vec2":
        self.x, self.y = v.x, v.y
        return self

    def add(self, v: "Vec2", s: float = 1.0) -> "Vec2":
        self.x += v.x * s
        self.y += v.y * s
        return self

    def addVectors(self, a: "Vec2", b: "Vec2") -> "Vec2":
        self.x, self.y = a.x + b.x, a.y + b.y
        return self

    def subtractVectors(self, a: "Vec2", b: "Vec2") -> "Vec2":
        self.x, self.y = a.x - b.x, a.y - b.y
        return self

    def scale(self, s: float) -> "Vec2":
        self.x *= s
        self.y *= s
        return self

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def lengthSq(self) -> float:
        return self.x * self.x + self.y * self.y

    def dot(self, v: "Vec2") -> float:
        return self.x * v.x + self.y * v.y

    def cross(self, v: "Vec2") -> float:
        """W 3D iloczyn wektorowy daje wektor; w 2D - skalar (składową z)."""
        return self.x * v.y - self.y * v.x

    def rotate(self, angle: float) -> "Vec2":
        """Zastępuje applyQuaternion(rot); obrót o -angle zastępuje invRot."""
        c, s = math.cos(angle), math.sin(angle)
        self.x, self.y = c * self.x - s * self.y, s * self.x + c * self.y
        return self

    def rotated(self, angle: float) -> "Vec2":
        return self.clone().rotate(angle)

    def isFinite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)

def normalizeAngle(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi