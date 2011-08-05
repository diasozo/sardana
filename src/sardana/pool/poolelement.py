#!/usr/bin/env python

##############################################################################
##
## This file is part of Sardana
##
## http://www.tango-controls.org/static/sardana/latest/doc/html/index.html
##
## Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
## 
## Sardana is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Sardana is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public License
## along with Sardana.  If not, see <http://www.gnu.org/licenses/>.
##
##############################################################################

"""This module is part of the Python Pool libray. It defines the base classes
for"""

__all__ = [ "PoolBaseElement", "PoolElement" ]

__docformat__ = 'restructuredtext'

import weakref
import functools

from poolevent import EventType
from poolbase import PoolObject


class PoolBaseElement(PoolObject):
    """A Pool object that besides the name, reference to the pool, ID, full_name
    and user_full_name has:
       
       - _simulation_mode : boolean telling if in simulation mode
       - _state : element state
       - _status : element status"""

    def __init__(self, **kwargs):
        self._simulation_mode = False
        self._state = None
        self._state_event = None
        self._status = None
        self._status_event = None
        self._action_cache = None
        super(PoolBaseElement, self).__init__(**kwargs)
    
    def get_action_cache(self):
        """Returns the internal action cache object"""
        return self._action_cache
    
    # --------------------------------------------------------------------------
    # state
    # --------------------------------------------------------------------------
    
    def get_state(self, cache=True, propagate=1):
        """Returns the state for this object. If cache is True (default) it
        returns the current state stored in cache (it will force an update if
        cache is empty). If propagate > 0 and if the state changed since last
        read, it will propagate the state event to all listeners.
        
            :param cache: tells if return value from local cache or update
                          from HW read [default: True]
            :type cache: bool
            :param propagate: if > 0 propagates the event in case it changed
                              since last HW read. Values bigger that mean the
                              event if sent should be a priority event
                              [default: 1]
            :type propagate: int
            :return: the current object state
            :rtype: :obj:`sardana.State`"""
        if not cache or self._state is None:
            state_info = self.read_state_info()
            self._set_state_info(state_info, propagate=propagate)
        return self._state
    
    def inspect_state(self):
        return self._state
    
    def set_state(self, state, propagate=1):
        self._set_state(state, propagate=propagate)
        
    def _set_state(self, state, propagate=1):
        self._state = state
        if not propagate:
            return
        if state == self._state_event:
            # current state is equal to last state_event. Skip event
            return
        self._state_event = state
        self.fire_event(EventType("state", priority=propagate), state)
    
    def put_state(self, state):
        self._state = state

    state = property(get_state, set_state, doc="element state")
    
    # --------------------------------------------------------------------------
    # status
    # --------------------------------------------------------------------------
    
    def get_status(self, cache=True, propagate=1):
        if not cache or self._status is None:
            state_info = self.read_state_info()
            self._set_state_info(state_info, propagate=propagate)
        return self._status
    
    def set_status(self, status, propagate=1):
        self._set_status(status, propagate=propagate)
        
    def _set_status(self, status, propagate=1):
        self._status = status
        if not propagate:
            return
        s_evt = self._status_event
        if s_evt is not None and len(status) == len(s_evt) and status == s_evt:
            # current status is equal to last status_event. Skip event
            return
        self._status_event = status
        self.fire_event(EventType("status", priority=propagate), status)
    
    def put_status(self, status):
        self._status = status
    
    status = property(get_status, set_status, doc="element status")
    
    # --------------------------------------------------------------------------
    # state information
    # --------------------------------------------------------------------------

    def set_state_info(self, state_info, propagate=1):
        self._set_state_info(state_info, propagate=propagate)
        
    def _set_state_info(self, state_info, propagate=1):
        state, status = state_info
        self._set_state(state, propagate=propagate)
        self._set_status(status, propagate=propagate)
    
    def read_state_info(self):
        ctrl_state_info = self._action_cache.read_state_info(serial=True)[self]
        return self._from_ctrl_state_info(ctrl_state_info)
    
    def put_state_info(self, state_info):
        self.put_state(state_info[0])
        self.put_status(state_info[1])
        
    def _from_ctrl_state_info(self, state_info):
        state, status = state_info[:2]
        state = int(state)
        return state, status


class PoolElement(PoolBaseElement):
    """A Pool element is an Pool object which is controlled by a controller.
       Therefore it contains a _ctrl_id and a _axis (the id of the element in
       the controller)."""
    
    def __init__(self, **kwargs):
        self._aborted = False
        ctrl = kwargs.pop('ctrl')
        self._ctrl = weakref.ref(ctrl)
        self._axis = kwargs.pop('axis')
        self._ctrl_id = ctrl.get_id()
        try:
            instrument = kwargs.pop('instrument')
            self.set_instrument(instrument)
        except KeyError:
            self._instrument = None
        super(PoolElement, self).__init__(**kwargs)

    def __repr__(self):
        data = {'name' : self.name, 'full_name': self.full_name,
                'ctrl_name' : self.controller.name, 'axis' : self.axis,
                'type' : self.controller.get_ctrl_type_names()[0] }
        res = "{name} ({full_name}) ({ctrl_name}/{axis}) {type}".format(**data)
        return res

    def get_controller(self):
        if self._ctrl is None:
            return None
        return self._ctrl()
    
    def get_controller_id(self):
        return self._ctrl_id
    
    def get_axis(self):
        return self._axis
    
    def set_action_cache(self, action_cache):
        self._action_cache = action_cache
        action_cache.add_element(self)
        
    # --------------------------------------------------------------------------
    # instrument
    # --------------------------------------------------------------------------
    
    def get_instrument(self):
        if self._instrument is None:
            return None
        return self._instrument()
    
    def set_instrument(self, instrument, propagate=1):
        self._set_instrument(instrument, propagate=propagate)
    
    def _set_instrument(self, instrument, propagate=1):
        if self._instrument is not None:
            self._instrument().remove_element(self)
        new_instrument_name = ""
        if instrument is None:
            self._instrument = None
        else:
            self._instrument = weakref.ref(instrument)
            new_instrument_name = instrument.full_name
            instrument.add_element(self)
        if not propagate:
            return
        self.fire_event(EventType("instrument", priority=propagate),
                        new_instrument_name)

    # --------------------------------------------------------------------------
    # abort
    # --------------------------------------------------------------------------
    
    def abort(self):
        self.controller.ctrl.AbortOne(self.axis)
        self._aborted = True
    
    def was_aborted(self):
        return self._aborted
    
    axis = property(get_axis, doc="element axis")
    
    controller = property(get_controller, doc="element controller")
    controller_id = property(get_controller_id, doc="element controller id")
    
    instrument = property(get_instrument, set_instrument, doc="element instrument")
    
