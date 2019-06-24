"""Resource Manager"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import random

from xs2clientprotocol import sc2api_pb2 as sc_pb

from tstarbot.building import BaseBuildingMgr


class DancingDronesMgr(BaseBuildingMgr):
  def __init__(self, dc):
    super(DancingDronesMgr, self).__init__(dc)
    self._range_high = 5
    self._range_low = -5
    self._move_ability = 1

  def update(self, dc, am):
    super(DancingDronesMgr, self).update(dc, am)

    drone_ids = dc.get_drones()
    pos = dc.get_hatcherys()

    print('pos=', pos)
    actions = self.move_drone_random_round_hatchery(drone_ids, pos[0])

    am.push_actions(actions)

  def move_drone_random_round_hatchery(self, drone_ids, pos):
    actions = []
    for drone in drone_ids:
      action = sc_pb.Action()
      action.action_raw.unit_command.ability_id = self._move_ability
      x = pos[0] + random.randint(self._range_low, self._range_high)
      y = pos[1] + random.randint(self._range_low, self._range_high)
      action.action_raw.unit_command.target_world_space_pos.x = x
      action.action_raw.unit_command.target_world_space_pos.y = y
      action.action_raw.unit_command.unit_tags.append(drone)
      actions.append(action)
    return actions
