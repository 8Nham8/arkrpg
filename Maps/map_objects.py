from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


class TerrainType(Enum):
    default = auto()
    wall = auto()


class TriggerType(Enum):
    # triggers on unit moving onto the tile (mines, beartrap)
    ON_STEP = auto()
    # triggers when told to do so (c4)
    MANUAL = auto()
    # volatile traps that explode on destruction
    ON_DESTROY = auto()


@dataclass
class PlacedObject:
    # represents traps and such placed on tiles or attached to obstacles
    name: str
    trigger_type: TriggerType = TriggerType.ON_STEP
    damage: int = 0
    # 0 = single target/tile, 1+ gives it splash radius
    aoe_radius: int = 0
    # bypasses the is_tough flag on structures when doing damage
    is_heavy_damage: bool = False
    is_armed: bool = True
    # says who owns the trap
    owner: Optional[object] = None


@dataclass
# represents an arbitrary single tile on the map
class Tile:
    # tile position vars
    x: int
    y: int

    terrain: TerrainType = TerrainType.default
    # default elevation is zero, no bonus
    elevation: int = 0
    # potentially useful for doing damage checks
    is_cover: bool = False
    # default amount for how much it costs to be able to move through a tile
    movement_cost: int = 1
    # Hard blockable check, useful for things like walls
    is_passable: bool = True
    # for destructable tiles, this bool may be switched to true if higher tier destructive attacks are needed to destroy.
    # ie explosives, hammers, sledgehammers, etc
    is_tough: bool = False
    # Hard check to prevent some tiles from being destroyed
    is_destructible: bool = False
    # health of the tile
    hp: int = 0

    # Refernce to an entity/unit occupying the tile.
    occupant: Optional[object] = None

    # decvices such as bear traps and land mines placed on the ground
    placed_objects: List[PlacedObject] = field(default_factory=list)

    # checks to see if unit can move into the tile
    def can_enter(self) -> bool:
        return self.is_passable and self.occupant is None

    # applies damage to the tile, returns true if destroyed. tough files require a heavy attack to be destroyed
    def take_damage(self, damage_dealt: int, is_heavy_attack: bool = False) -> bool:
        if not self.is_destructible:
            return False

        if self.is_tough and not is_heavy_attack:
            return False

        self.hp = self.hp - damage_dealt
        if self.hp <= 0:
            self.destroy()
            return True
        return False

    # resets tile properties to a default ground tile when destroyed
    def destroy(self):
        self.is_destructible = False
        self.is_tough = False
        self.hp = 0
        self.is_passable = True
        self.is_cover = False
        self.movement_cost = 1
        self.terrain = TerrainType.default


@dataclass
# obstacles, props, hazards, etc. placed on tiles
class EnvironmentalObject:
    name: str
    # prevents movement through the tile
    blocks_movement: bool = False
    # prevents ranged attacks from going through the tile
    blocks_sight: bool = False
    # height of the cover. no defined system yet, but an example could be 1 acts as cover but can be shot over, 2 cannot be shot over
    height: int = 0

    # checks whether prop is destructable
    is_destructible: bool = False
    # checks whether prop requires a higher tier of damage to damage
    is_tough: bool = False
    # health of the object
    hp: int = 0

    # devices placed on the surface of this object
    attachments: List[PlacedObject] = field(default_factory=list)

    # basically same function as the tiles, true if destryed, false if not
    def take_damage(self, damage_dealt: int, is_heavy_attack: bool = False) -> bool:
        if not self.is_destructible:
            return False

        if self.is_tough and not is_heavy_attack:
            return False

        self.hp = self.hp - damage_dealt
        return self.hp <= 0


class GameMap:
    # container that manages the grid, queries, and spacial logic of the maps
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid: Dict[Tuple[int, int], Tile] = {}
        self.obstacles: Dict[Tuple[int, int], EnvironmentalObject] = {}
        self._generate_blank_map()

    # generate a blank map, but at the specified width and height
    def _generate_blank_map(self):
        for i in range(self.width):
            for j in range(self.height):
                self.grid[(i, j)] = Tile(x=i, y=j)

    # returns data for a given tile
    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        return self.grid.get((x, y))

    # check if a position is in bounds, returns a bool
    def check_in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    # place an obstacle at a given position
    def place_obstacle(self, x: int, y: int, obstacle: EnvironmentalObject):
        tile = self.get_tile(x, y)
        if tile:
            self.obstacles[(x, y)] = obstacle
            if obstacle.blocks_movement:
                tile.is_passable = False
            if obstacle.height > 0:
                tile.is_cover = True

    # place an object or trap on a tile ground
    def place_object_on_tile(self, x: int, y: int, obj: PlacedObject) -> bool:
        tile = self.get_tile(x, y)
        if tile:
            tile.placed_objects.append(obj)
            return True
        return False

    # attach an object or charge to an obstacle/wall
    def attach_object_to_obstacle(self, x: int, y: int, obj: PlacedObject) -> bool:
        if (x, y) in self.obstacles:
            self.obstacles[(x, y)].attachments.append(obj)
            return True
        return False

    # do damage to a structure. returns a string description of the result.
    # results are verbose for now, but this is unlikely to be the layer where we formulate text for the player
    def attack_tile_or_object(
        self, x: int, y: int, damage: int, is_heavy_attack: bool = False
    ) -> str:
        tile = self.get_tile(x, y)
        if not tile:
            return "Out of bounds"

        # check for props/obstacles on the tile first
        if (x, y) in self.obstacles:
            obstacle = self.obstacles[(x, y)]
            if obstacle.take_damage(damage, is_heavy_attack):
                del self.obstacles[(x, y)]
                tile.is_passable = True
                tile.is_cover = False
                return f"Destroyed {obstacle.name}"
            return f"Damaged {obstacle.name}. Remaining HP: {obstacle.hp}"

        # if no obstacle, attempt to damage the tile itself (ie breaking a wall)
        if tile.is_destructible:
            if tile.take_damage(damage, is_heavy_attack):
                return "Wall collapsed into passable rubble!"
            return f"Damaged wall tile. Remaining HP: {tile.hp}"

        return "Target is indestructible."