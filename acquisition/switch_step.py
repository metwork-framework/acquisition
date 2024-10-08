#!/usr/bin/env python3

import os
import hashlib
from acquisition.copy_step import AcquisitionCopyStep
from acquisition.utils import _get_or_make_trash_dir
from xattrfile import XattrFile
from acquisition.switch_rules import RulesReader, HardlinkAction, RulesSet

MFDATA_CURRENT_PLUGIN_DIR = os.environ.get("MFDATA_CURRENT_PLUGIN_DIR",
                                           "{{MFDATA_CURRENT_PLUGIN_DIR}}")
MFDATA_INTERNAL_PLUGINS_SWITCH_NO_MATCH_KEEP_ORIGINAL_BASENAME = \
    os.environ.get(
        "MFDATA_INTERNAL_PLUGINS_SWITCH_NO_MATCH_KEEP_ORIGINAL_BASENAME",
        "0").strip() == '1'


def md5sumfile(path):
    try:
        with open(path, 'r') as f:
            c = f.read()
    except Exception:
        return "empty"
    return hashlib.md5(c.encode('utf8')).hexdigest()


class AcquisitionSwitchStep(AcquisitionCopyStep):

    def _init(self):
        AcquisitionCopyStep._init(self)
        x = RulesReader()
        r = self.args.rules_file
        if not os.path.isfile(r):
            self.warning("rules_path value: %s is not a file => let's start "
                         "with an empty rules_set" % r)
            self.rules_set = RulesSet()
        else:
            self.rules_set = x.read(
                r, self.args.switch_section_prefix)
        self.md5sum = md5sumfile(r)
        self.no_match_policy = self.args.no_match_policy
        if self.no_match_policy not in ("delete", "keep"):
            raise Exception("invalid no_match_policy: %s "
                            "must be keep or delete" % self.no_match_policy)
        for plugin_name, step_name in self.rules_set.get_virtual_targets():
            self.add_virtual_trace(plugin_name, step_name)
        if self.no_match_policy == "keep":
            self.add_virtual_trace(">nomatch", "keep")
        else:
            self.add_virtual_trace(">nomatch", "delete")

    def add_extra_arguments(self, parser):
        AcquisitionCopyStep.add_extra_arguments(self, parser)
        parser.add_argument(
            '--rules-file', action='store',
            default="%s/config.ini" % MFDATA_CURRENT_PLUGIN_DIR,
            help="ini file path with rules")
        parser.add_argument(
            '--no-match-policy', action='store',
            default="delete",
            help="policy when no rules is matched: keep (keep files in a "
            "custom dedicated directory) or delete (default)")
        parser.add_argument(
            '--switch-section-prefix', action='store',
            default="switch_rules*",
            help="section prefix for switch rules")

    def ping(self):
        # Called every second
        if md5sumfile(self.args.rules_file) != self.md5sum:
            self.warning("my rules_file has been modified => let's quit to "
                         "force a restart")
            self.stop_flag = True

    def _keep(self, xaf):
        new_filename = xaf.basename()
        if MFDATA_INTERNAL_PLUGINS_SWITCH_NO_MATCH_KEEP_ORIGINAL_BASENAME:
            new_filename = \
                xaf.tags['first.core.original_basename'].decode('utf8')
        new_filepath = os.path.join(
            _get_or_make_trash_dir(self.plugin_name, "nomatch"),
            new_filename,
        )
        old_filepath = xaf.filepath
        success, moved = xaf.move_or_copy(new_filepath)
        if success:
            if moved:
                self.info("%s moved into %s", old_filepath, new_filepath)
            else:
                self.info("%s copied into %s", xaf.filepath, new_filepath)
            tags_filepath = new_filepath + ".tags"
            xaf.write_tags_in_a_file(tags_filepath)
            XattrFile(new_filepath).clear_tags()
            self.add_trace(xaf, ">nomatch", "keep")

    def before_copy(self, xaf):
        actions = self.rules_set.evaluate(xaf)
        self.info("%i actions matched for file=%s" % (len(actions),
                                                      xaf.filepath))
        if len(actions) == 0:
            if self.no_match_policy == "keep":
                self._keep(xaf)
            else:
                # delete
                self.info("Deleting %s" % xaf.filepath)
                xaf.delete_or_nothing()
                self.add_trace(xaf, ">nomatch", "delete")
            return None
        res = []
        for action in actions:
            hardlink = isinstance(action, HardlinkAction)
            res.append((action.plugin_name, action.step_name, hardlink))
        return res


def main():
    x = AcquisitionSwitchStep()
    x.run()
