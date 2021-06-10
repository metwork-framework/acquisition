import fnmatch
import re
import os
import importlib
import sys
import time
from mflog import get_logger
from opinionated_configparser import OpinionatedConfigParser

LOGGER = get_logger("switch/rules")


class add_sys_path():

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        if self.path is not None and self.path != "":
            sys.path.insert(0, self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if self.path is not None and self.path != "":
                sys.path.remove(self.path)
        except ValueError:
            pass


class BadSyntax(Exception):

    pass


class Action(object):

    def __init__(self, plugin_name, step_name):
        self.plugin_name = plugin_name
        self.step_name = step_name

    def __hash__(self):
        return hash((self.__class__.__name__,
                    self.plugin_name, self.step_name))


class CopyAction(Action):

    def __str__(self):
        return "copy to %s/%s" % (self.plugin_name, self.step_name)


class HardlinkAction(Action):

    def __str__(self):
        return "hardlink to %s/%s" % (self.plugin_name, self.step_name)


class SwitchRule(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)


class RulesBlock(object):

    def __init__(self, params=[]):
        self.params = params
        self.switch_rules = []

    def add_switch_rule(self, switch_rule):
        self.switch_rules.append(switch_rule)

    def eval(self, xaf, rule_pattern):
        raise NotImplementedError()

    def evaluate(self, xaf):
        actions = set()
        for rule in self.switch_rules:
            try:
                res = self.eval(xaf, rule.pattern)
            except Exception:
                LOGGER.exception("exception during rule block %s eval on %s" %
                                 (self, rule.pattern))
            else:
                if res:
                    LOGGER.debug("=> adding actions: %s" %
                                 ", ".join([str(x) for x in rule.actions]))
                    actions = actions.union(rule.actions)
        return (actions, len(self.switch_rules))

    def get_virtual_targets(self):
        targets = set()
        for rule in self.switch_rules:
            for action in rule.actions:
                targets.add((action.plugin_name, action.step_name))
        return targets


class OneParameterRulesBlock(RulesBlock):

    def __init__(self, params=[]):
        RulesBlock.__init__(self, params)
        if len(params) != 1:
            raise Exception("This rules block must have exactly one argument")

    def get_val_from_xaf(self, xaf):
        return xaf.tags.get(self.params[0], b"{NOT_FOUND}").decode('utf8')


class ZeroParameterRulesBlock(RulesBlock):

    def __init__(self, params=[]):
        RulesBlock.__init__(self, params)
        if len(params) != 0:
            raise Exception("This rules block must have zero argument")


class FnmatchRulesBlock(OneParameterRulesBlock):

    def eval(self, xaf, rule_pattern):
        val = self.get_val_from_xaf(xaf)
        res = fnmatch.fnmatch(val, rule_pattern)
        LOGGER.debug("fnmatch.fnmatch(%s, %s) switch rule => %s" %
                     (val, rule_pattern, res))
        return res


class NotfnmatchRulesBlock(FnmatchRulesBlock):

    def eval(self, xaf, rule_pattern):
        parent = FnmatchRulesBlock.eval(self, xaf, rule_pattern)
        return not parent


class EqualRulesBlock(OneParameterRulesBlock):

    def eval(self, xaf, rule_pattern):
        val = self.get_val_from_xaf(xaf)
        res = (val == rule_pattern)
        LOGGER.debug("(%s == %s) switch rule => %s" %
                     (val, rule_pattern, res))
        return res


class NotequalRulesBlock(EqualRulesBlock):

    def eval(self, xaf, rule_pattern):
        parent = EqualRulesBlock.eval(self, xaf, rule_pattern)
        return not parent


class RegexRulesBlock(OneParameterRulesBlock):

    def eval(self, xaf, rule_pattern):
        val = self.get_val_from_xaf(xaf)
        res = re.match(val, rule_pattern)
        LOGGER.debug("re.match(%s, %s) switch rule => %s" %
                     (val, rule_pattern, res))
        return res


class NotregexRulesBlock(RegexRulesBlock):

    def eval(self, xaf, rule_pattern):
        parent = RegexRulesBlock.eval(self, xaf, rule_pattern)
        return not parent


class AlwaystrueRulesBlock(ZeroParameterRulesBlock):

    def eval(self, xaf, rule_pattern):
        LOGGER.debug("alwaystrue switch rule => True")
        return True


class PythonRulesBlock(ZeroParameterRulesBlock):

    def __init__(self, *args, **kwargs):
        ZeroParameterRulesBlock.__init__(self, *args, **kwargs)
        self._funcs = {}

    def get_func(self, rule_pattern):
        if rule_pattern not in self._funcs:
            if ":" in rule_pattern:
                sys_path = rule_pattern.split(':')[0]
                func_path = rule_pattern.split(':')[1]
            else:
                sys_path = ""
                func_path = rule_pattern
            func_name = func_path.split('.')[-1]
            module_path = ".".join(func_path.split('.')[0:-1])
            with add_sys_path(sys_path):
                importlib.invalidate_caches()
                spec = importlib.util.spec_from_file_location(
                    "my_custom_function",
                    os.path.join(sys_path, module_path + ".py")
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                func = getattr(mod, func_name)
                self._funcs[rule_pattern] = func
        return self._funcs[rule_pattern]

    def eval(self, xaf, rule_pattern):
        func = self.get_func(rule_pattern)
        before = time.time()
        res = func(xaf)
        after = time.time()
        if (after - before) > 1.0:
            LOGGER.warning("more than 1s passed in %s function", func)
        LOGGER.debug("%s(xaf) switch rule => %s" % (func, res))
        return res


class RulesSet(object):

    def __init__(self):
        self.rule_blocks = []

    def add_rules_block(self, rule_block):
        self.rule_blocks.append(rule_block)

    def evaluate(self, xaf):
        actions = set()
        total_rules = 0
        before = time.time()
        for rule_block in self.rule_blocks:
            res, rules_count = rule_block.evaluate(xaf)
            actions = actions.union(res)
            total_rules = total_rules + rules_count
        after = time.time()
        LOGGER.debug("%i rules evaluated in a total of %i ms",
                     total_rules, int(1000.0 * (after - before)))
        return actions

    def get_virtual_targets(self):
        targets = set()
        for rule_block in self.rule_blocks:
            targets = targets.union(rule_block.get_virtual_targets())
        return targets


class RulesReader(object):

    def __init__(self):
        self.log = LOGGER
        self._raw_lines = []

    def rules_block_factory(self, rule_type, params=[]):
        c = "%sRulesBlock" % rule_type.capitalize()
        try:
            klass = globals()[c]
            return klass(params)
        except Exception:
            self.log.exception("probably a wrong rules block type: %s" %
                               rule_type)
            raise BadSyntax()

    def action_factory(self, action_type, *args, **kwargs):
        c = "%sAction" % action_type.capitalize()
        try:
            klass = globals()[c]
            return klass(*args, **kwargs)
        except Exception:
            self.log.exception("probably a wrong action type: %s" %
                               action_type)
            raise BadSyntax()

    def read(self, path, section_prefix="switch_rules*"):
        self.log = self.log.bind(path=path)
        result = RulesSet()
        x = OpinionatedConfigParser(delimiters=("=",), comment_prefixes=("#",))
        x.optionxform = str
        x.read([path])
        rules_block = None
        for section in x.sections():
            if fnmatch.fnmatch(section, "%s:*:*" % section_prefix):
                tempo = section.split(':')
                typ = tempo[1]
                params = ':'.join(tempo[2:]).split(',')
                rules_block = self.rules_block_factory(typ, params)
                result.add_rules_block(rules_block)
            elif fnmatch.fnmatch(section, "%s:*" % section_prefix):
                tempo = section.split(':')
                typ = tempo[1]
                rules_block = self.rules_block_factory(typ)
                result.add_rules_block(rules_block)
            else:
                continue
            for option in x.options(section):
                val = x.get(section, option)
                actions = [y.strip() for y in val.split(',')]
                pattern = option.replace('@@@@@@', '=').replace('~~~~~~', '#')
                switch_rule = SwitchRule(pattern)
                for action in actions:
                    tempo2 = action.split('/')
                    if len(tempo2) == 2:
                        if tempo2[1].endswith('*'):
                            act = self.action_factory("hardlink", tempo2[0],
                                                      tempo2[1][:-1])
                        else:
                            act = self.action_factory("copy", tempo2[0],
                                                      tempo2[1])
                    else:
                        self.log.error("bad action [%s] for section [%s] "
                                       "and pattern: %s" % (action, section,
                                                            option))
                        raise BadSyntax()
                    switch_rule.add_action(act)
                rules_block.add_switch_rule(switch_rule)
        return result
