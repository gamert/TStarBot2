"""Building Manager"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from random import choice

from pyxs2.lib.typeenums import UNIT_TYPEID
from pyxs2.lib.typeenums import ABILITY_ID

from tstarbot.production_strategy.build_cmd import BuildCmdUnit
from tstarbot.production_strategy.build_cmd import BuildCmdUpgrade
from tstarbot.production_strategy.build_cmd import BuildCmdMorph
from tstarbot.production_strategy.build_cmd import BuildCmdBuilding
from tstarbot.production_strategy.build_cmd import BuildCmdExpand
from tstarbot.production_strategy.build_cmd import BuildCmdSpawnLarva
from tstarbot.data.pool.macro_def import WORKER_BUILD_ABILITY
from tstarbot.building.placer import create_placer
from tstarbot.util import collect_units_by_type_alliance
from tstarbot.util import find_nearest_l1
from tstarbot.util import act_build_by_self
from tstarbot.util import act_build_by_tag
from tstarbot.util import act_build_by_pos
from tstarbot.util import act_move_to_pos


def is_building(unit):
  """  """
  if unit.orders:
    return unit.orders[0].ability_id in WORKER_BUILD_ABILITY
  return False


class BaseBuildingMgr(object):
  def __init__(self, dc):
    pass

  def update(self, dc, am):
    pass

  def reset(self):
    pass


class ZergBuildingMgr(BaseBuildingMgr):
  def __init__(self, dc):
    super(ZergBuildingMgr, self).__init__(dc)
    self.verbose = 0
    self._step = 0
    self._placer_name = 'naive_predef'
    self._placer_verbose = 0
    self.TT = dc.sd.TT  # tech tree

    self._init_config(dc)  # do it last, as it overwrites previous members

    self._placer = create_placer(self._placer_name)
    self._placer.verbose = self._placer_verbose

  def reset(self):
    self._placer.reset()
    self._step = 0

  def update(self, dc, am):
    super(ZergBuildingMgr, self).update(dc, am)

    if self.verbose >= 2:
      units = dc.sd.obs['units']
      all_larva = collect_units_by_type_alliance(units,
                                                 UNIT_TYPEID.ZERG_LARVA.value)
      all_queen = collect_units_by_type_alliance(units,
                                                 UNIT_TYPEID.ZERG_QUEEN.value)
      print('ZergBuildingMgr: step = {}'.format(self._step))
      print('len commands = {}'.format(dc.dd.build_command_queue.size()))
      print('len queen = {}'.format(len(all_queen)))
      print('len larva = {}'.format(len(all_larva)))

    self._step += 1

    if dc.dd.build_command_queue.empty():
      return

    accepted_cmds = [
      BuildCmdUnit,
      BuildCmdUpgrade,
      BuildCmdMorph,
      BuildCmdBuilding,
      BuildCmdExpand,
      BuildCmdSpawnLarva
    ]
    actions = []
    for _ in range(dc.dd.build_command_queue.size()):
      cmd = dc.dd.build_command_queue.get()
      if type(cmd) not in accepted_cmds:
        # put back unknown command
        dc.dd.build_command_queue.put(cmd)
        continue
      action = None
      if type(cmd) == BuildCmdUnit:
        action = self._build_unit(cmd, dc)
      elif type(cmd) == BuildCmdUpgrade:
        action = self._build_upgrade_tech(cmd, dc)
      elif type(cmd) == BuildCmdMorph:
        action = self._build_morph(cmd, dc)
      elif type(cmd) == BuildCmdBuilding:
        action = self._build_building(cmd, dc)
      elif type(cmd) == BuildCmdExpand:
        action = self._build_base_expand_v2(cmd, dc)
      elif type(cmd) == BuildCmdSpawnLarva:
        action = self._spawn_larva(cmd, dc)
      if action:
        actions.append(action)
    am.push_actions(actions)

  def _init_config(self, dc):
    if hasattr(dc, 'config'):
      if hasattr(dc.config, 'building_verbose'):
        self.verbose = dc.config.building_verbose
      if hasattr(dc.config, 'building_placer'):
        self._placer_name = dc.config.building_placer
      if hasattr(dc.config, 'building_placer_verbose'):
        self._placer_verbose = dc.config.building_placer_verbose

  def _build_unit(self, cmd, dc):
    base_instance = dc.dd.base_pool.bases[cmd.base_tag]
    if not base_instance:
      if self.verbose >= 1:
        print(
          "Warning: ZergBuildingMgr._build_unit: "
          "base_tag {} invalid in base_pool".format(cmd.base_tag)
        )
      return None
    ability_id = self.TT.getUnitData(cmd.unit_type).buildAbility
    if cmd.unit_type == UNIT_TYPEID.ZERG_QUEEN.value:
      return act_build_by_self(builder_tag=cmd.base_tag,
                               ability_id=ability_id)
    else:
      if not base_instance.larva_set:
        if self.verbose >= 1:
          print("Warning: ZergBuildingMgr._build_unit: "
                "empty larva set".format(cmd.base_tag))
        return None
      larva_tag = choice(list(base_instance.larva_set))
      return act_build_by_self(builder_tag=larva_tag,
                               ability_id=ability_id)

  def _build_upgrade_tech(self, cmd, dc):
    builder_tag = cmd.building_tag
    ability_id = cmd.ability_id
    return act_build_by_self(builder_tag, ability_id)

  def _build_morph(self, cmd, dc):
    builder_tag = cmd.unit_tag
    ability_id = cmd.ability_id
    if self.verbose >= 1:
      if ability_id == ABILITY_ID.MORPH_LURKERDEN.value:
        print('building MORPH_LURKERDEN')
      if ability_id == ABILITY_ID.MORPH_LURKER.value:
        print('morphing lurker')
      if ability_id == ABILITY_ID.MORPH_GREATERSPIRE.value:
        print('morphing greater spire')
      if ability_id == ABILITY_ID.MORPH_BROODLORD.value:
        print('morphing broodlord')
    return act_build_by_self(builder_tag, ability_id)

  def _build_building(self, cmd, dc):
    unit_type = cmd.unit_type
    ability_id = self.TT.getUnitData(unit_type).buildAbility

    builder_tag, target_tag = self._can_build_by_tag(cmd, dc)
    if builder_tag and target_tag:
      return act_build_by_tag(
        builder_tag, target_tag, ability_id)

    builder_tag, target_pos = self._can_build_by_pos(cmd, dc)
    if builder_tag and target_pos:
      return act_build_by_pos(
        builder_tag, target_pos, ability_id)

    # TODO: use logger
    if self.verbose >= 1:
      print(
        "Warning: ZergBuildingMgr._build_building: "
        "cannot handle building command {}".format(cmd)
      )
    return None

  def _can_build_by_tag(self, cmd, dc):
    builder_tag, target_tag = None, None
    unit_type = cmd.unit_type
    if unit_type == UNIT_TYPEID.ZERG_EXTRACTOR.value:
      base_instance = dc.dd.base_pool.bases[cmd.base_tag]
      if base_instance:
        builder_tag = self._find_available_worker_for_building(
          dc, base_instance)
        target_tag = self._find_available_gas(dc, base_instance)
    return builder_tag, target_tag

  def _can_build_by_pos(self, cmd, dc):
    builder_tag, target_pos = None, ()
    if hasattr(cmd, 'base_tag') and hasattr(cmd, 'unit_type'):
      base_instance = dc.dd.base_pool.bases[cmd.base_tag]
      builder_tag = self._find_available_worker_for_building(
        dc, base_instance)

      self._placer.update(dc)
      target_pos = self._placer.get_planned_pos(cmd, dc)
    return builder_tag, target_pos

  def _build_base_expand(self, cmd, dc):
    base_instance = dc.dd.base_pool.bases[cmd.base_tag]
    if base_instance:
      builder_tag = self._find_available_worker_for_building(
        dc, base_instance)
      if builder_tag:
        target_pos = cmd.pos
        ability_id = ABILITY_ID.BUILD_HATCHERY.value
        return act_build_by_pos(builder_tag, target_pos, ability_id)
    if self.verbose >= 1:
      print(
        "Warning: ZergBuildingMgr._build_base_expand: "
        "invalid base_tag in base_pool or no worker around this base"
      )
    return None

  def _build_base_expand_v2(self, cmd, dc):
    """ when expanding, pre-move a worker to the target location when
     possible """

    if cmd.builder_tag is not None:
      builder_tag = cmd.builder_tag
    else:
      base_instance = dc.dd.base_pool.bases[cmd.base_tag]
      builder_tag = self._find_available_worker_for_building(
        dc, base_instance)
    if builder_tag and builder_tag in dc.dd.worker_pool.workers:
      target_pos = cmd.pos
      player_info = dc.sd.obs['player']
      base_data = self.TT.getUnitData(UNIT_TYPEID.ZERG_HATCHERY.value)
      if player_info[1] >= base_data.mineralCost:
        ability_id = ABILITY_ID.BUILD_HATCHERY.value
        return act_build_by_pos(builder_tag, target_pos, ability_id)
      else:
        cmd_n = BuildCmdExpand(base_tag=cmd.base_tag, pos=cmd.pos,
                               builder_tag=builder_tag)
        dc.dd.build_command_queue.put(cmd_n)
        return act_move_to_pos(builder_tag, target_pos)
    if self.verbose >= 1:
      print(
        "Warning: ZergBuildingMgr._build_base_expand: "
        "invalid base_tag in base_pool or no worker around this base"
      )
    return None

  def _find_available_worker_for_building(self, dc, base_instance):
    # find a worker, which must be not building, for the building task
    # the found worker can be idle, harvesting mineral/gas, etc.
    for w_tag in base_instance.worker_set:
      w_unit = dc.dd.worker_pool.get_by_tag(w_tag).unit
      if w_unit and not is_building(w_unit):
        return w_tag
    return None

  def _find_available_gas(self, dc, base_instance):
    # find a vacant vespene/gas on which there is NO extractor
    for gas_tag in base_instance.gas_set:
      gas_unit = dc.dd.base_pool.vespenes[gas_tag]
      vb_units = [v for _, v in dc.dd.base_pool.vbs.items()]
      vb_unit = find_nearest_l1(vb_units, gas_unit)
      if not vb_unit:
        # not a single extractor at all; this gas must be vacant
        return gas_tag
      dx = vb_unit.float_attr.pos_x - gas_unit.float_attr.pos_x
      dy = vb_unit.float_attr.pos_y - gas_unit.float_attr.pos_y
      if abs(dx) > 0.5 or abs(dy) > 0.5:
        return gas_tag
    return None

  def _spawn_larva(self, cmd, dc):
    # queen injects larva on a base
    builder_tag = cmd.queen_tag
    target_tag = cmd.base_tag
    ability_id = ABILITY_ID.EFFECT_INJECTLARVA.value
    return act_build_by_tag(builder_tag, target_tag, ability_id)
