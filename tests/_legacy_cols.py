# -*- coding: utf-8 -*-
"""Restores the column set every test was written against — before the defaults changed to Name, Start, Finish, Duration,
% Complete, Predecessors, Resource, Status (Task Mode, WBS and the Actual dates now start hidden; the Gantt list shows
only Name, Start, Finish, Duration, % Complete). A suite that merely needs Task Mode / WBS / the Actual columns visible,
in the old order, runs this right after its first load; the suites that test the defaults themselves do not."""
LEGACY_COLS = """() => {
  const T = ['mode', 'wbs', 'name', 'start', 'end', 'actualStart', 'actualFinish', 'duration', 'progress', 'preds', 'status'];
  const G = ['mode', 'wbs', 'name', 'start', 'end', 'duration', 'baselineStart', 'baselineFinish', 'durationVariance'];
  const tail = c => DEFAULT_COL_ORDER.filter(x => !c.includes(x));
  colOrder = ['mode', 'wbs', 'name', 'start', 'end', 'actualStart', 'actualFinish', 'duration', 'progress', 'preds', 'remaining', 'status', 'resource', ...DEFAULT_COL_ORDER.filter(x => !['mode', 'wbs', 'name', 'start', 'end', 'actualStart', 'actualFinish', 'duration', 'progress', 'preds', 'remaining', 'status', 'resource'].includes(x))];
  colHidden = new Set(DEFAULT_COL_ORDER.filter(x => !T.includes(x)));
  gColOrder = [...colOrder]; gColHidden = new Set(DEFAULT_COL_ORDER.filter(x => !G.includes(x)));
  save(); render();
}"""
