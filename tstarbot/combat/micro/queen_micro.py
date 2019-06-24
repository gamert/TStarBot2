import math

import numpy as np
from pyxs2.lib.typeenums import UNIT_TYPEID, ABILITY_ID, UPGRADE_ID
from xs2clientprotocol import sc2api_pb2 as sc_pb

from tstarbot.combat.micro.micro_base import MicroBase
from tstarbot.data.queue.combat_command_queue import CombatCmdType
from tstarbot.data.pool.macro_def import COMBAT_ANTI_AIR_UNITS


class QueenMgr(MicroBase):
  """ A zvz Zerg combat manager """

  def __init__(self):
    super(QueenMgr, self).__init__()
    self.cure_range = 15

  @staticmethod
  def cure_target(u, target):
    action = sc_pb.Action()
    action.action_raw.unit_command.ability_id = \
      ABILITY_ID.EFFECT_TRANSFUSION.value
    action.action_raw.unit_command.target_unit_tag = target.tag
    action.action_raw.unit_command.unit_tags.append(u.tag)
    return action

  def find_weakest_unit(self, u, units, dist):
    min_a = None
    min_hp = 10000
    for a in units:
      if self.dist_between_units_with_radius(u,
                                             a) < dist and 0 < a.float_attr.health < min_hp:
        min_a = a
        min_hp = a.float_attr.health
    return min_a

  def is_queen_run_away(self, u, closest_enemy):
    closest_enemy_dist = self.dist_between_units(u, closest_enemy)
    if closest_enemy_dist < self.roach_attack_range:
      return True
    return False

  def hit_and_run(self, u, pos):
    action = self.attack_pos(u, pos)
    if len(self.enemy_combat_units) > 0:
      closest_enemy = self.find_closest_enemy(u, self.enemy_combat_units)
      if self.is_queen_run_away(u, closest_enemy):
        action = self.run_away_from_closest_enemy(u, closest_enemy)
      else:
        action = self.attack_pos(u, pos)
    return action

  def act(self, u, pos, mode):
    action = self.hit_and_run(u, pos)

    if u.float_attr.energy > 50:

      spine_crawlers = [a for a in self.self_combat_units
                        if a.int_attr.unit_type ==
                        UNIT_TYPEID.ZERG_SPINECRAWLER.value]
      roaches = [a for a in self.self_combat_units
                 if a.int_attr.unit_type == UNIT_TYPEID.ZERG_ROACH.value]

      weakest_spine_crawler = self.find_weakest_unit(u, spine_crawlers,
                                                     self.cure_range)
      weakest_roach = self.find_weakest_unit(u, roaches, self.cure_range)

      if weakest_spine_crawler is not None and \
          weakest_spine_crawler.float_attr.health_max - \
          weakest_spine_crawler.float_attr.health >= 125:
        action = self.cure_target(u, weakest_spine_crawler)
        return action
      if weakest_roach is not None and \
          weakest_roach.float_attr.health_max - \
          weakest_roach.float_attr.health >= 125:
        action = self.cure_target(u, weakest_roach)
        return action

    return action
